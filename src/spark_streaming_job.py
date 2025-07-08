import os
import sys
import json
import joblib
import numpy as np
from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AnomalyDetectionStreaming:
    def __init__(self, kafka_host='localhost:9092', topic_name='sensor-data', 
                 output_path='output/anomalies', checkpoint_path='checkpoints/anomaly_detection'):
        """
        Initialize the Spark Streaming job for real-time anomaly detection
        
        Args:
            kafka_host (str): Kafka broker host and port
            topic_name (str): Kafka topic to consume from
            output_path (str): Path to write anomaly results
            checkpoint_path (str): Checkpoint location for Spark streaming
        """
        self.kafka_host = kafka_host
        self.topic_name = topic_name
        self.output_path = output_path
        self.checkpoint_path = checkpoint_path
        
        # Initialize Spark session
        self.spark = self._create_spark_session()
        
        # Load the trained model and preprocessing components
        self.model, self.scaler, self.imputer, self.feature_columns = self._load_model_and_preprocessing()
        
        # Broadcast the model and preprocessing objects for efficient distribution
        self.model_broadcast = self.spark.sparkContext.broadcast(self.model)
        self.scaler_broadcast = self.spark.sparkContext.broadcast(self.scaler)
        self.imputer_broadcast = self.spark.sparkContext.broadcast(self.imputer)
        self.feature_columns_broadcast = self.spark.sparkContext.broadcast(self.feature_columns)
    
    def _create_spark_session(self):
        """Create and configure Spark session"""
        try:
            spark = SparkSession.builder \
                .appName("SECOM_Anomaly_Detection_Streaming") \
                .config("spark.sql.adaptive.enabled", "true") \
                .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
                .config("spark.sql.streaming.forceDeleteTempCheckpointLocation", "true") \
                .getOrCreate()
            
            spark.sparkContext.setLogLevel("WARN")
            logger.info("Spark session created successfully")
            return spark
            
        except Exception as e:
            logger.error(f"Failed to create Spark session: {e}")
            raise
    
    def _load_model_and_preprocessing(self):
        """Load the trained model and preprocessing components"""
        try:
            # Load the trained model
            model_path = os.path.join('models', 'model.joblib')
            model = joblib.load(model_path)
            
            # Load preprocessing components
            scaler_path = os.path.join('models', 'scaler.joblib')
            scaler = joblib.load(scaler_path)
            
            imputer_path = os.path.join('models', 'imputer.joblib')
            imputer = joblib.load(imputer_path)
            
            # Load model metadata to get feature columns
            metadata_path = os.path.join('models', 'model_metadata.joblib')
            metadata = joblib.load(metadata_path)
            feature_columns = metadata['feature_columns']
            
            logger.info(f"Loaded model with {len(feature_columns)} features")
            return model, scaler, imputer, feature_columns
            
        except Exception as e:
            logger.error(f"Failed to load model and preprocessing components: {e}")
            raise
    
    def predict_anomaly(self, features_dict):
        """
        Predict anomaly for a single sample using the trained model
        
        Args:
            features_dict (dict): Dictionary of feature values
            
        Returns:
            tuple: (is_anomaly, anomaly_score)
        """
        try:
            # Extract features in the correct order
            feature_values = []
            for col in self.feature_columns_broadcast.value:
                value = features_dict.get(str(col), np.nan)
                feature_values.append(float(value) if value is not None else np.nan)
            
            # Convert to numpy array and reshape for single prediction
            X = np.array(feature_values).reshape(1, -1)
            
            # Apply preprocessing (imputation and scaling are already done during training)
            # The features should already be preprocessed when they come from the producer
            
            # Predict anomaly
            prediction = self.model_broadcast.value.predict(X)[0]
            anomaly_score = self.model_broadcast.value.decision_function(X)[0]
            
            # Convert prediction (-1 for anomaly, 1 for normal) to boolean
            is_anomaly = prediction == -1
            
            return bool(is_anomaly), float(anomaly_score)
            
        except Exception as e:
            logger.error(f"Error in anomaly prediction: {e}")
            return False, 0.0
    
    def create_prediction_udf(self):
        """Create a UDF for anomaly prediction"""
        
        def predict_udf(features_json):
            try:
                # Parse the features JSON
                features_dict = json.loads(features_json) if features_json else {}
                
                # Predict anomaly
                is_anomaly, anomaly_score = self.predict_anomaly(features_dict)
                
                return {
                    'is_anomaly': is_anomaly,
                    'anomaly_score': anomaly_score,
                    'prediction_timestamp': datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Error in UDF prediction: {e}")
                return {
                    'is_anomaly': False,
                    'anomaly_score': 0.0,
                    'prediction_timestamp': datetime.utcnow().isoformat(),
                    'error': str(e)
                }
        
        # Define return schema for the UDF
        prediction_schema = StructType([
            StructField("is_anomaly", BooleanType(), True),
            StructField("anomaly_score", DoubleType(), True),
            StructField("prediction_timestamp", StringType(), True),
            StructField("error", StringType(), True)
        ])
        
        return udf(predict_udf, prediction_schema)
    
    def process_stream(self, output_mode='append', trigger_interval='10 seconds'):
        """
        Process the Kafka stream and perform real-time anomaly detection
        
        Args:
            output_mode (str): Output mode for streaming ('append', 'complete', 'update')
            trigger_interval (str): Trigger interval for processing
        """
        
        logger.info(f"Starting stream processing from topic: {self.topic_name}")
        
        try:
            # Create the prediction UDF
            predict_anomaly_udf = self.create_prediction_udf()
            
            # Read from Kafka
            kafka_df = self.spark \
                .readStream \
                .format("kafka") \
                .option("kafka.bootstrap.servers", self.kafka_host) \
                .option("subscribe", self.topic_name) \
                .option("startingOffsets", "latest") \
                .option("failOnDataLoss", "false") \
                .load()
            
            # Parse the JSON messages
            parsed_df = kafka_df.select(
                col("key").cast("string").alias("message_key"),
                col("value").cast("string").alias("message_value"),
                col("timestamp").alias("kafka_timestamp"),
                col("partition"),
                col("offset")
            )
            
            # Extract data from JSON
            json_schema = StructType([
                StructField("timestamp", StringType(), True),
                StructField("sample_id", IntegerType(), True),
                StructField("producer_timestamp", StringType(), True),
                StructField("features", StringType(), True)  # Keep as string for UDF
            ])
            
            data_df = parsed_df.select(
                col("message_key"),
                col("kafka_timestamp"),
                col("partition"),
                col("offset"),
                from_json(col("message_value"), json_schema).alias("data")
            ).select(
                col("message_key"),
                col("kafka_timestamp"),
                col("partition"),
                col("offset"),
                col("data.timestamp").alias("sample_timestamp"),
                col("data.sample_id"),
                col("data.producer_timestamp"),
                col("data.features").alias("features_json")
            )
            
            # Apply anomaly detection
            predictions_df = data_df.withColumn(
                "prediction",
                predict_anomaly_udf(col("features_json"))
            ).select(
                col("message_key"),
                col("sample_timestamp"),
                col("sample_id"),
                col("producer_timestamp"),
                col("kafka_timestamp"),
                col("prediction.is_anomaly"),
                col("prediction.anomaly_score"),
                col("prediction.prediction_timestamp"),
                col("prediction.error"),
                col("partition"),
                col("offset")
            )
            
            # Filter for anomalies only (optional - comment out to see all predictions)
            anomalies_df = predictions_df.filter(col("is_anomaly") == True)
            
            # Write to console for monitoring
            console_query = predictions_df \
                .writeStream \
                .outputMode(output_mode) \
                .format("console") \
                .option("truncate", False) \
                .option("numRows", 20) \
                .trigger(processingTime=trigger_interval) \
                .start()
            
            # Write anomalies to file
            file_query = anomalies_df \
                .writeStream \
                .outputMode("append") \
                .format("json") \
                .option("path", self.output_path) \
                .option("checkpointLocation", self.checkpoint_path) \
                .trigger(processingTime=trigger_interval) \
                .start()
            
            logger.info("Stream processing started successfully")
            
            # Wait for termination
            console_query.awaitTermination()
            
        except Exception as e:
            logger.error(f"Error in stream processing: {e}")
            raise
    
    def stop(self):
        """Stop the Spark session"""
        if self.spark:
            self.spark.stop()
            logger.info("Spark session stopped")

def main():
    """Main function to run the streaming job"""
    import argparse
    
    parser = argparse.ArgumentParser(description='SECOM Anomaly Detection Streaming Job')
    parser.add_argument('--kafka-host', default='localhost:9092',
                       help='Kafka broker host:port (default: localhost:9092)')
    parser.add_argument('--topic', default='sensor-data',
                       help='Kafka topic name (default: sensor-data)')
    parser.add_argument('--output-path', default='output/anomalies',
                       help='Output path for anomaly results')
    parser.add_argument('--checkpoint-path', default='checkpoints/anomaly_detection',
                       help='Checkpoint location for Spark streaming')
    parser.add_argument('--trigger-interval', default='10 seconds',
                       help='Trigger interval for processing (default: 10 seconds)')
    
    args = parser.parse_args()
    
    # Create output directories
    os.makedirs(args.output_path, exist_ok=True)
    os.makedirs(args.checkpoint_path, exist_ok=True)
    
    # Create and run the streaming job
    streaming_job = AnomalyDetectionStreaming(
        kafka_host=args.kafka_host,
        topic_name=args.topic,
        output_path=args.output_path,
        checkpoint_path=args.checkpoint_path
    )
    
    try:
        streaming_job.process_stream(trigger_interval=args.trigger_interval)
    except KeyboardInterrupt:
        logger.info("Streaming job interrupted by user")
    finally:
        streaming_job.stop()

if __name__ == "__main__":
    main() 