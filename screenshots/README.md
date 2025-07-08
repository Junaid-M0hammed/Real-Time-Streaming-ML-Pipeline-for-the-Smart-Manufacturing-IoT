# Dashboard Screenshots

This directory contains screenshots of the Real-Time Anomaly Detection Dashboard.

## How to Capture Screenshots

1. **Start the Dashboard**:
   ```bash
   docker-compose up -d
   # Or manually: streamlit run src/streamlit_dashboard.py
   ```

2. **Access the Dashboard**: Open http://localhost:8501 in your browser

3. **Capture Screenshots**:
   - `dashboard_overview.png` - Main dashboard with metrics and alerts
   - `time_series_chart.png` - Time series anomaly visualization
   - `analytics_distribution.png` - Statistical analysis and distributions
   - `operational_metrics.png` - Production line metrics
   - `system_monitoring.png` - System health and Kafka monitoring

## Screenshot Guidelines

- Use high resolution (1920x1080 or higher)
- Capture with some sample data running
- Include both normal and anomaly detection states
- Show interactive elements and real-time updates
- Keep UI clean and professional looking

## Current Status

📋 **TODO**: Add actual dashboard screenshots
- The dashboard is currently running on http://localhost:8501
- Screenshots should be captured while the system is processing live data
- Each screenshot should demonstrate different features of the system 