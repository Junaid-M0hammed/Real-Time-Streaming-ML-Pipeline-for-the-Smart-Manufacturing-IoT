import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
import joblib
import os

def preprocess_secom_data():
    """
    Preprocess the SECOM dataset:
    - Load raw data
    - Handle missing values
    - Normalize features
    - Add timestamps
    - Save preprocessed data
    """
    
    # Load the raw SECOM data
    print("Loading SECOM dataset...")
    data_path = os.path.join('data', 'secom.data')
    
    # Read the data (space-separated values)
    df = pd.read_csv(data_path, sep=' ', header=None)
    
    print(f"Dataset shape: {df.shape}")
    print(f"Missing values: {df.isnull().sum().sum()}")
    
    # Handle missing values using median imputation
    print("Handling missing values...")
    imputer = SimpleImputer(strategy='median')
    df_imputed = pd.DataFrame(imputer.fit_transform(df), columns=df.columns)
    
    # Save the imputer for later use
    joblib.dump(imputer, os.path.join('models', 'imputer.joblib'))
    
    # Normalize features using StandardScaler
    print("Normalizing features...")
    scaler = StandardScaler()
    df_scaled = pd.DataFrame(scaler.fit_transform(df_imputed), columns=df_imputed.columns)
    
    # Save the scaler for later use
    joblib.dump(scaler, os.path.join('models', 'scaler.joblib'))
    
    # Add timestamp column (simulate real-time data)
    print("Adding timestamps...")
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    timestamps = [start_time + timedelta(seconds=i*10) for i in range(len(df_scaled))]
    df_scaled['timestamp'] = timestamps
    
    # Add a sample_id column
    df_scaled['sample_id'] = range(len(df_scaled))
    
    # Reorder columns to have timestamp and sample_id first
    cols = ['timestamp', 'sample_id'] + [col for col in df_scaled.columns if col not in ['timestamp', 'sample_id']]
    df_final = df_scaled[cols]
    
    # Save preprocessed data
    output_path = os.path.join('data', 'secom_preprocessed.csv')
    df_final.to_csv(output_path, index=False)
    
    print(f"Preprocessed data saved to: {output_path}")
    print(f"Final dataset shape: {df_final.shape}")
    print(f"Columns: {list(df_final.columns[:5])}... (showing first 5)")
    
    return df_final

if __name__ == "__main__":
    # Create models directory if it doesn't exist
    os.makedirs('models', exist_ok=True)
    
    # Preprocess the data
    preprocessed_data = preprocess_secom_data()
    print("\nData preprocessing completed successfully!")
    print(f"Sample data preview:\n{preprocessed_data.head()}") 