#!/usr/bin/env python3
"""
Generate sample anomaly data for dashboard testing
"""

import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def generate_sample_anomalies():
    """Generate sample anomaly detection results for dashboard testing"""
    
    print("🔧 Generating sample anomaly data for dashboard testing...")
    
    # Create output directory
    output_dir = "output/anomalies"
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate sample data for the last 24 hours
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)
    
    # Generate timestamps every 10 seconds for richer data
    timestamps = []
    current_time = start_time
    while current_time <= end_time:
        timestamps.append(current_time)
        current_time += timedelta(seconds=10)
    
    sample_anomalies = []
    
    for i, timestamp in enumerate(timestamps):
        # Create more realistic patterns
        hour = timestamp.hour
        
        # Simulate different anomaly rates during different shifts
        if 6 <= hour < 14:  # Day shift - lower anomaly rate
            base_anomaly_rate = 0.08
        elif 14 <= hour < 22:  # Evening shift - normal anomaly rate
            base_anomaly_rate = 0.12
        else:  # Night shift - higher anomaly rate (fatigue, fewer operators)
            base_anomaly_rate = 0.18
        
        # Add some random variation
        anomaly_rate = base_anomaly_rate + random.uniform(-0.03, 0.03)
        is_anomaly = random.random() < anomaly_rate
        
        if is_anomaly:
            # Anomalies have more extreme scores with variety
            if random.random() < 0.3:  # 30% severe anomalies
                anomaly_score = random.uniform(-0.25, -0.15)
            else:  # 70% moderate anomalies
                anomaly_score = random.uniform(-0.15, -0.05)
        else:
            # Normal samples with some variation
            anomaly_score = random.uniform(-0.05, 0.06)
            
        # Add some temporal correlation (anomalies tend to cluster)
        if i > 0 and len(sample_anomalies) > 0 and sample_anomalies[-1]['is_anomaly'] and random.random() < 0.4:
            is_anomaly = True
            anomaly_score = random.uniform(-0.18, -0.08)
        
        # Add more realistic metadata
        severity = "HIGH" if anomaly_score < -0.15 else "MEDIUM" if anomaly_score < -0.08 else "LOW"
        line_id = f"LINE_{random.randint(1, 5)}"
        station_id = f"ST_{random.randint(10, 50)}"
        
        sample_record = {
            "message_key": f"sample_{i}",
            "sample_timestamp": (timestamp - timedelta(seconds=random.randint(0, 10))).isoformat(),
            "sample_id": i,
            "producer_timestamp": timestamp.isoformat(),
            "kafka_timestamp": timestamp.isoformat(),
            "is_anomaly": is_anomaly,
            "anomaly_score": anomaly_score,
            "prediction_timestamp": timestamp.isoformat(),
            "error": None,
            "partition": 0,
            "offset": i,
            "severity": severity if is_anomaly else "NORMAL",
            "line_id": line_id,
            "station_id": station_id,
            "shift": "DAY" if 6 <= hour < 14 else "EVENING" if 14 <= hour < 22 else "NIGHT"
        }
        
        sample_anomalies.append(sample_record)
    
    # Filter to only anomalies (like our Spark job does)
    anomalies_only = [record for record in sample_anomalies if record["is_anomaly"]]
    
    print(f"Generated {len(sample_anomalies)} total samples, {len(anomalies_only)} anomalies")
    
    # Write to multiple JSON files (simulating Spark output over time)
    chunk_size = len(anomalies_only) // 5  # Split into 5 files
    files_created = []
    
    for i in range(5):
        start_idx = i * chunk_size
        end_idx = start_idx + chunk_size if i < 4 else len(anomalies_only)
        chunk = anomalies_only[start_idx:end_idx]
        
        if chunk:  # Only create file if there's data
            output_file = os.path.join(output_dir, f"part-{i:05d}-anomalies.json")
            with open(output_file, 'w') as f:
                for record in chunk:
                    f.write(json.dumps(record) + '\n')
            files_created.append(output_file)
    
    print(f"✅ Sample anomaly data written to {len(files_created)} files")
    print(f"📊 Anomaly rate: {len(anomalies_only)/len(sample_anomalies)*100:.1f}%")
    print(f"📊 Severity breakdown:")
    
    # Analyze severity distribution
    severity_counts = {}
    for record in anomalies_only:
        severity = record.get('severity', 'UNKNOWN')
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
    
    for severity, count in severity_counts.items():
        percentage = (count / len(anomalies_only)) * 100
        print(f"   {severity}: {count} ({percentage:.1f}%)")
    
    return files_created

if __name__ == "__main__":
    generate_sample_anomalies()
    print("🎯 Ready to test dashboard! Run: streamlit run src/streamlit_dashboard.py") 