import pandas as pd
import json
import time
import argparse
from kafka import KafkaProducer
from kafka.errors import KafkaError
import os
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SECOMDataProducer:
    def __init__(self, kafka_host='localhost:9092', topic_name='sensor-data'):
        """
        Initialize the Kafka producer for SECOM data streaming
        
        Args:
            kafka_host (str): Kafka broker host and port
            topic_name (str): Kafka topic name to send data to
        """
        self.kafka_host = kafka_host
        self.topic_name = topic_name
        self.producer = None
        self.data = None
        
        # Initialize Kafka producer
        self._init_producer()
        
        # Load preprocessed data
        self._load_data()
    
    def _init_producer(self):
        """Initialize the Kafka producer with appropriate configuration"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=[self.kafka_host],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda v: v.encode('utf-8') if v else None,
                acks='all',  # Wait for all replicas to acknowledge
                retries=3,
                batch_size=16384,
                linger_ms=10,
                buffer_memory=33554432,
                compression_type='gzip'
            )
            logger.info(f"Kafka producer initialized successfully. Connected to: {self.kafka_host}")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            raise
    
    def _load_data(self):
        """Load the preprocessed SECOM dataset"""
        try:
            data_path = os.path.join('data', 'secom_preprocessed.csv')
            self.data = pd.read_csv(data_path)
            logger.info(f"Loaded dataset with {len(self.data)} samples and {len(self.data.columns)} features")
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise
    
    def create_message(self, row):
        """
        Create a message from a data row
        
        Args:
            row: Pandas series representing a single data sample
            
        Returns:
            dict: Message to be sent to Kafka
        """
        # Convert numpy types to native Python types for JSON serialization
        message = {
            'timestamp': str(row['timestamp']),
            'sample_id': int(row['sample_id']),
            'producer_timestamp': datetime.utcnow().isoformat(),
            'features': {}
        }
        
        # Add all feature columns (excluding timestamp and sample_id)
        feature_cols = [col for col in self.data.columns if col not in ['timestamp', 'sample_id']]
        for col in feature_cols:
            value = row[col]
            # Handle NaN values and convert numpy types
            if pd.isna(value):
                message['features'][str(col)] = None
            else:
                message['features'][str(col)] = float(value)
        
        return message
    
    def send_message(self, message, key=None):
        """
        Send a message to the Kafka topic
        
        Args:
            message (dict): The message to send
            key (str): Optional message key
        """
        try:
            future = self.producer.send(
                self.topic_name,
                value=message,
                key=key
            )
            
            # Get the result to check for errors
            record_metadata = future.get(timeout=10)
            logger.debug(f"Message sent to topic: {record_metadata.topic}, "
                        f"partition: {record_metadata.partition}, "
                        f"offset: {record_metadata.offset}")
            return True
            
        except KafkaError as e:
            logger.error(f"Failed to send message: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")
            return False
    
    def stream_data(self, rate_per_second=1, repeat=False, max_messages=None):
        """
        Stream the SECOM data to Kafka
        
        Args:
            rate_per_second (float): Number of messages to send per second
            repeat (bool): Whether to repeat the dataset when finished
            max_messages (int): Maximum number of messages to send (None for unlimited)
        """
        logger.info(f"Starting data streaming to topic '{self.topic_name}' at {rate_per_second} msg/sec")
        
        sleep_time = 1.0 / rate_per_second
        messages_sent = 0
        total_errors = 0
        
        try:
            while True:
                for idx, row in self.data.iterrows():
                    # Check if we've reached the maximum number of messages
                    if max_messages and messages_sent >= max_messages:
                        logger.info(f"Reached maximum number of messages: {max_messages}")
                        return
                    
                    # Create and send message
                    message = self.create_message(row)
                    key = f"sample_{row['sample_id']}"
                    
                    success = self.send_message(message, key)
                    
                    if success:
                        messages_sent += 1
                        if messages_sent % 100 == 0:
                            logger.info(f"Sent {messages_sent} messages, errors: {total_errors}")
                    else:
                        total_errors += 1
                    
                    # Sleep to maintain the desired rate
                    time.sleep(sleep_time)
                
                # If not repeating, break after one pass through the data
                if not repeat:
                    break
                
                logger.info(f"Completed one pass through the dataset. Repeating...")
        
        except KeyboardInterrupt:
            logger.info("Streaming interrupted by user")
        except Exception as e:
            logger.error(f"Error during streaming: {e}")
        finally:
            self.close()
            logger.info(f"Streaming completed. Total messages sent: {messages_sent}, errors: {total_errors}")
    
    def close(self):
        """Close the Kafka producer"""
        if self.producer:
            self.producer.flush()
            self.producer.close()
            logger.info("Kafka producer closed")

def main():
    """Main function to run the Kafka producer"""
    parser = argparse.ArgumentParser(description='SECOM Data Kafka Producer')
    parser.add_argument('--kafka-host', default='localhost:9092', 
                       help='Kafka broker host:port (default: localhost:9092)')
    parser.add_argument('--topic', default='sensor-data',
                       help='Kafka topic name (default: sensor-data)')
    parser.add_argument('--rate', type=float, default=1.0,
                       help='Messages per second (default: 1.0)')
    parser.add_argument('--repeat', action='store_true',
                       help='Repeat the dataset continuously')
    parser.add_argument('--max-messages', type=int,
                       help='Maximum number of messages to send')
    
    args = parser.parse_args()
    
    # Create and run the producer
    producer = SECOMDataProducer(kafka_host=args.kafka_host, topic_name=args.topic)
    producer.stream_data(
        rate_per_second=args.rate,
        repeat=args.repeat,
        max_messages=args.max_messages
    )

if __name__ == "__main__":
    main() 