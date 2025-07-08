import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import os
import matplotlib.pyplot as plt
import seaborn as sns

def train_anomaly_detection_model():
    """
    Train an Isolation Forest model for anomaly detection on SECOM data
    """
    
    # Load preprocessed data
    print("Loading preprocessed data...")
    data_path = os.path.join('data', 'secom_preprocessed.csv')
    df = pd.read_csv(data_path)
    
    print(f"Dataset shape: {df.shape}")
    print(f"Columns: {list(df.columns[:5])}... (showing first 5)")
    
    # Prepare features (exclude timestamp and sample_id)
    feature_cols = [col for col in df.columns if col not in ['timestamp', 'sample_id']]
    X = df[feature_cols].values
    
    print(f"Training features shape: {X.shape}")
    
    # Train Isolation Forest
    print("Training Isolation Forest model...")
    
    # Configure Isolation Forest
    isolation_forest = IsolationForest(
        contamination=0.1,  # Assume 10% of data are anomalies
        random_state=42,
        n_estimators=100,
        max_samples='auto',
        max_features=1.0,
        bootstrap=False,
        n_jobs=-1,
        verbose=1
    )
    
    # Fit the model
    isolation_forest.fit(X)
    
    # Predict anomalies (-1 for anomalies, 1 for normal)
    predictions = isolation_forest.predict(X)
    anomaly_scores = isolation_forest.decision_function(X)
    
    # Convert predictions to binary (1 for anomaly, 0 for normal)
    is_anomaly = (predictions == -1).astype(int)
    
    # Add predictions to dataframe for analysis
    df['anomaly_score'] = anomaly_scores
    df['is_anomaly'] = is_anomaly
    
    # Print statistics
    n_anomalies = sum(is_anomaly)
    anomaly_rate = n_anomalies / len(df)
    
    print(f"\nModel Training Results:")
    print(f"Total samples: {len(df)}")
    print(f"Detected anomalies: {n_anomalies}")
    print(f"Anomaly rate: {anomaly_rate:.2%}")
    print(f"Anomaly score range: [{anomaly_scores.min():.4f}, {anomaly_scores.max():.4f}]")
    
    # Save the trained model
    model_path = os.path.join('models', 'model.joblib')
    joblib.dump(isolation_forest, model_path)
    print(f"Model saved to: {model_path}")
    
    # Save model metadata
    metadata = {
        'model_type': 'IsolationForest',
        'contamination': 0.1,
        'n_estimators': 100,
        'feature_count': len(feature_cols),
        'training_samples': len(df),
        'detected_anomalies': n_anomalies,
        'anomaly_rate': anomaly_rate,
        'feature_columns': feature_cols
    }
    
    metadata_path = os.path.join('models', 'model_metadata.joblib')
    joblib.dump(metadata, metadata_path)
    print(f"Model metadata saved to: {metadata_path}")
    
    # Create visualizations
    create_visualizations(df, anomaly_scores, is_anomaly)
    
    return isolation_forest, metadata

def create_visualizations(df, anomaly_scores, is_anomaly):
    """
    Create visualizations for the anomaly detection results
    """
    
    print("Creating visualizations...")
    
    # Create plots directory
    plots_dir = os.path.join('models', 'plots')
    os.makedirs(plots_dir, exist_ok=True)
    
    # 1. Anomaly score distribution
    plt.figure(figsize=(12, 4))
    
    plt.subplot(1, 2, 1)
    plt.hist(anomaly_scores, bins=50, alpha=0.7, color='blue', edgecolor='black')
    plt.xlabel('Anomaly Score')
    plt.ylabel('Frequency')
    plt.title('Distribution of Anomaly Scores')
    plt.grid(True, alpha=0.3)
    
    # 2. Anomaly detection over time
    plt.subplot(1, 2, 2)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Plot normal points
    normal_mask = is_anomaly == 0
    plt.scatter(df[normal_mask]['timestamp'], df[normal_mask]['anomaly_score'], 
               c='blue', alpha=0.6, s=10, label='Normal')
    
    # Plot anomalies
    anomaly_mask = is_anomaly == 1
    plt.scatter(df[anomaly_mask]['timestamp'], df[anomaly_mask]['anomaly_score'], 
               c='red', alpha=0.8, s=20, label='Anomaly')
    
    plt.xlabel('Timestamp')
    plt.ylabel('Anomaly Score')
    plt.title('Anomaly Detection Over Time')
    plt.legend()
    plt.xticks(rotation=45)
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, 'anomaly_analysis.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    # 3. Feature importance (using variance of features for anomalies vs normal)
    feature_cols = [col for col in df.columns if col not in ['timestamp', 'sample_id', 'anomaly_score', 'is_anomaly']]
    
    if len(feature_cols) > 0:
        # Calculate feature statistics for normal vs anomaly samples
        normal_data = df[df['is_anomaly'] == 0][feature_cols]
        anomaly_data = df[df['is_anomaly'] == 1][feature_cols]
        
        # Calculate mean differences
        mean_diff = np.abs(anomaly_data.mean() - normal_data.mean())
        top_features = mean_diff.nlargest(20)
        
        plt.figure(figsize=(12, 8))
        top_features.plot(kind='barh')
        plt.xlabel('Mean Absolute Difference')
        plt.title('Top 20 Features by Mean Difference (Anomaly vs Normal)')
        plt.tight_layout()
        plt.savefig(os.path.join(plots_dir, 'feature_importance.png'), dpi=300, bbox_inches='tight')
        plt.close()
    
    print(f"Visualizations saved to: {plots_dir}")

if __name__ == "__main__":
    # Create models directory if it doesn't exist
    os.makedirs('models', exist_ok=True)
    
    # Train the model
    model, metadata = train_anomaly_detection_model()
    print("\nModel training completed successfully!")
    print(f"Model metadata: {metadata}") 