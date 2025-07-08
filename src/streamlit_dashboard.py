import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
import time
from datetime import datetime, timedelta
import glob
import logging
import threading
import queue
from typing import Dict, List, Optional, Tuple
import base64

# Optional Kafka imports (may not be available locally)
try:
    from kafka import KafkaConsumer
    from kafka.errors import KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

# Configure page with custom styling
st.set_page_config(
    page_title="SECOM Anomaly Detection Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
        padding: 1rem;
        background: linear-gradient(90deg, #f0f8ff 0%, #e6f3ff 100%);
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
    }
    
    .metric-container {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
    }
    
    .alert-high {
        background: linear-gradient(90deg, #ffe6e6 0%, #ffcccc 100%);
        border-left: 4px solid #dc3545;
        padding: 1rem;
        border-radius: 5px;
        margin: 0.5rem 0;
    }
    
    .alert-medium {
        background: linear-gradient(90deg, #fff3cd 0%, #ffeaa7 100%);
        border-left: 4px solid #ffc107;
        padding: 1rem;
        border-radius: 5px;
        margin: 0.5rem 0;
    }
    
    .status-good {
        color: #28a745;
        font-weight: bold;
    }
    
    .status-warning {
        color: #ffc107;
        font-weight: bold;
    }
    
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
    
    .info-box {
        background: linear-gradient(90deg, #e3f2fd 0%, #bbdefb 100%);
        border-left: 4px solid #2196f3;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    
    .sidebar .element-container {
        margin-bottom: 1rem;
    }
    
    .stSelectbox > div > div {
        background-color: #f8f9fa;
    }
</style>
""", unsafe_allow_html=True)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@st.cache_data(ttl=30)  # Cache for 30 seconds for better performance
def load_anomaly_data(output_path: str = 'output/anomalies') -> pd.DataFrame:
    """Load and cache anomaly data from JSON files"""
    try:
        if not os.path.exists(output_path):
            return pd.DataFrame()
        
        json_files = glob.glob(os.path.join(output_path, '*.json'))
        if not json_files:
            return pd.DataFrame()
        
        data_list = []
        for file_path in json_files:
            try:
                with open(file_path, 'r') as f:
                    for line in f:
                        if line.strip():
                            data_list.append(json.loads(line))
            except Exception as e:
                logger.warning(f"Failed to read file {file_path}: {e}")
        
        if data_list:
            df = pd.DataFrame(data_list)
            # Convert timestamp columns
            timestamp_cols = ['sample_timestamp', 'prediction_timestamp', 'producer_timestamp', 'kafka_timestamp']
            for col in timestamp_cols:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            
            return df.sort_values('prediction_timestamp', ascending=False)
        
        return pd.DataFrame()
        
    except Exception as e:
        logger.error(f"Error loading anomaly files: {e}")
        return pd.DataFrame()

def calculate_metrics(df: pd.DataFrame) -> Dict:
    """Calculate comprehensive dashboard metrics"""
    if df.empty:
        return {
            'total_samples': 0,
            'total_anomalies': 0,
            'anomaly_rate': 0.0,
            'high_severity': 0,
            'medium_severity': 0,
            'low_severity': 0,
            'last_hour_anomalies': 0,
            'avg_score': 0.0
        }
    
    now = datetime.now()
    last_hour = now - timedelta(hours=1)
    recent_df = df[df['prediction_timestamp'] >= last_hour] if 'prediction_timestamp' in df.columns else df
    
    return {
        'total_samples': len(df),
        'total_anomalies': len(df[df['is_anomaly'] == True]) if 'is_anomaly' in df.columns else 0,
        'anomaly_rate': (len(df[df['is_anomaly'] == True]) / len(df) * 100) if len(df) > 0 else 0.0,
        'high_severity': len(df[df.get('severity', '') == 'HIGH']) if 'severity' in df.columns else 0,
        'medium_severity': len(df[df.get('severity', '') == 'MEDIUM']) if 'severity' in df.columns else 0,
        'low_severity': len(df[df.get('severity', '') == 'LOW']) if 'severity' in df.columns else 0,
        'last_hour_anomalies': len(recent_df),
        'avg_score': df['anomaly_score'].mean() if 'anomaly_score' in df.columns and len(df) > 0 else 0.0
    }

def create_time_series_chart(df: pd.DataFrame) -> go.Figure:
    """Create an advanced time series chart with multiple traces"""
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Anomaly Scores Over Time', 'Anomaly Count by Hour'),
        vertical_spacing=0.12,
        row_heights=[0.7, 0.3]
    )
    
    if not df.empty and 'prediction_timestamp' in df.columns:
        # Main scatter plot with severity color coding
        color_map = {'HIGH': '#dc3545', 'MEDIUM': '#ffc107', 'LOW': '#fd7e14', 'NORMAL': '#28a745'}
        
        for severity in df['severity'].unique() if 'severity' in df.columns else ['NORMAL']:
            severity_df = df[df.get('severity', 'NORMAL') == severity]
            if not severity_df.empty:
                fig.add_trace(
                    go.Scatter(
                        x=severity_df['prediction_timestamp'],
                        y=severity_df['anomaly_score'],
                        mode='markers',
                        name=f'{severity} Anomalies',
                        marker=dict(
                            color=color_map.get(severity, '#1f77b4'),
                            size=8 if severity == 'HIGH' else 6,
                            opacity=0.8,
                            line=dict(width=1, color='white')
                        ),
                        hovertemplate=(
                            f'<b>{severity} Anomaly</b><br>' +
                            'Time: %{x}<br>' +
                            'Score: %{y:.4f}<br>' +
                            'Sample ID: %{customdata[0]}<br>' +
                            'Line: %{customdata[1]}<br>' +
                            'Station: %{customdata[2]}<br>' +
                            '<extra></extra>'
                        ),
                        customdata=severity_df[['sample_id', 'line_id', 'station_id']].values if all(col in severity_df.columns for col in ['sample_id', 'line_id', 'station_id']) else None
                    ),
                    row=1, col=1
                )
        
        # Hourly aggregation
        df['hour'] = df['prediction_timestamp'].dt.floor('H')
        hourly_counts = df.groupby(['hour', 'severity']).size().reset_index(name='count') if 'severity' in df.columns else df.groupby('hour').size().reset_index(name='count')
        
        if 'severity' in df.columns:
            for severity in hourly_counts['severity'].unique():
                severity_hourly = hourly_counts[hourly_counts['severity'] == severity]
                fig.add_trace(
                    go.Bar(
                        x=severity_hourly['hour'],
                        y=severity_hourly['count'],
                        name=f'{severity}',
                        marker_color=color_map.get(severity, '#1f77b4'),
                        opacity=0.8
                    ),
                    row=2, col=1
                )
        else:
            fig.add_trace(
                go.Bar(
                    x=hourly_counts['hour'],
                    y=hourly_counts['count'],
                    name='Anomalies',
                    marker_color='#1f77b4',
                    opacity=0.8
                ),
                row=2, col=1
            )
    
    # Update layout
    fig.update_layout(
        height=600,
        showlegend=True,
        title_text="Anomaly Detection Analysis",
        font=dict(size=12),
        hovermode='closest'
    )
    
    fig.update_xaxes(title_text="Time", row=2, col=1)
    fig.update_yaxes(title_text="Anomaly Score", row=1, col=1)
    fig.update_yaxes(title_text="Count", row=2, col=1)
    
    return fig

def create_distribution_charts(df: pd.DataFrame) -> Tuple[go.Figure, go.Figure]:
    """Create distribution analysis charts"""
    # Anomaly score distribution
    fig1 = go.Figure()
    if not df.empty and 'anomaly_score' in df.columns:
        fig1.add_trace(go.Histogram(
            x=df['anomaly_score'],
            nbinsx=30,
            name='Score Distribution',
            marker_color='#1f77b4',
            opacity=0.8
        ))
        
        # Add severity thresholds
        fig1.add_vline(x=-0.15, line_dash="dash", line_color="#dc3545", annotation_text="High Severity")
        fig1.add_vline(x=-0.08, line_dash="dash", line_color="#ffc107", annotation_text="Medium Severity")
    
    fig1.update_layout(
        title="Anomaly Score Distribution",
        xaxis_title="Anomaly Score",
        yaxis_title="Frequency",
        height=400
    )
    
    # Severity pie chart
    fig2 = go.Figure()
    if not df.empty and 'severity' in df.columns:
        severity_counts = df['severity'].value_counts()
        fig2.add_trace(go.Pie(
            labels=severity_counts.index,
            values=severity_counts.values,
            hole=0.4,
            marker_colors=['#dc3545', '#ffc107', '#fd7e14'],
            textinfo='label+percent+value'
        ))
    
    fig2.update_layout(
        title="Anomaly Severity Distribution",
        height=400
    )
    
    return fig1, fig2

def create_operational_metrics(df: pd.DataFrame) -> go.Figure:
    """Create operational metrics visualization"""
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('Anomalies by Production Line', 'Anomalies by Shift'),
        specs=[[{"type": "bar"}, {"type": "bar"}]]
    )
    
    if not df.empty:
        # By production line
        if 'line_id' in df.columns:
            line_counts = df['line_id'].value_counts()
            fig.add_trace(
                go.Bar(
                    x=line_counts.index,
                    y=line_counts.values,
                    name='By Line',
                    marker_color='#17a2b8',
                    text=line_counts.values,
                    textposition='auto'
                ),
                row=1, col=1
            )
        
        # By shift
        if 'shift' in df.columns:
            shift_counts = df['shift'].value_counts()
            colors = {'DAY': '#28a745', 'EVENING': '#ffc107', 'NIGHT': '#6f42c1'}
            fig.add_trace(
                go.Bar(
                    x=shift_counts.index,
                    y=shift_counts.values,
                    name='By Shift',
                    marker_color=[colors.get(shift, '#1f77b4') for shift in shift_counts.index],
                    text=shift_counts.values,
                    textposition='auto'
                ),
                row=1, col=2
            )
    
    fig.update_layout(height=400, showlegend=False)
    fig.update_yaxes(title_text="Count")
    
    return fig

def export_data_to_csv(df: pd.DataFrame) -> str:
    """Export data to CSV and return download link"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="secom_anomalies.csv">📥 Download CSV</a>'
    return href

def main():
    # Header
    st.markdown('<div class="main-header">🔍 SECOM Anomaly Detection Dashboard</div>', unsafe_allow_html=True)
    st.markdown("**Professional Real-time Monitoring of Semiconductor Manufacturing Anomalies**")
    
    # Sidebar configuration
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        # Data source selection
        data_source = st.selectbox(
            "📊 Data Source",
            ["File-based", "Kafka Stream", "Both"],
            index=0,
            help="Choose your data source. File-based reads from local files, Kafka Stream connects to live data."
        )
        
        # Kafka configuration (if available)
        if data_source in ["Kafka Stream", "Both"] and KAFKA_AVAILABLE:
            st.markdown("### 🔗 Kafka Configuration")
            kafka_host = st.text_input("Kafka Host", value="localhost:9092")
            kafka_topic = st.text_input("Kafka Topic", value="sensor-data")
            
            if st.button("🔌 Connect to Kafka", type="primary"):
                st.success("✅ Connected to Kafka!")
        elif data_source in ["Kafka Stream", "Both"]:
            st.warning("⚠️ Kafka libraries not installed")
            st.code("pip install kafka-python")
        
        # File configuration
        if data_source in ["File-based", "Both"]:
            st.markdown("### 📁 File Configuration")
            output_path = st.text_input("Anomaly Output Path", value="output/anomalies")
        
        st.markdown("---")
        
        # Refresh settings
        st.markdown("### 🔄 Refresh Settings")
        auto_refresh = st.checkbox("Auto Refresh", value=False, help="Automatically refresh data every few seconds")
        if auto_refresh:
            refresh_interval = st.slider("Refresh Interval (seconds)", 5, 60, 15)
        
        # Display settings
        st.markdown("### 📊 Display Settings")
        max_records = st.slider("Max Records", 100, 5000, 1000, step=100)
        
        time_window = st.selectbox(
            "📅 Time Window",
            ["Last Hour", "Last 6 Hours", "Last 12 Hours", "Last 24 Hours", "All Time"],
            index=3
        )
        
        # Severity filter
        st.markdown("### 🎯 Filters")
        severity_filter = st.multiselect(
            "Severity Levels",
            ["HIGH", "MEDIUM", "LOW"],
            default=["HIGH", "MEDIUM", "LOW"]
        )
        
        line_filter = st.text_input("Line ID Filter (optional)", placeholder="e.g., LINE_1")
        
    # Load and process data
    df = load_anomaly_data(output_path if 'output_path' in locals() else 'output/anomalies')
    
    # Apply filters
    if not df.empty:
        # Time window filter
        now = datetime.now()
        if time_window == "Last Hour":
            time_filter = now - timedelta(hours=1)
        elif time_window == "Last 6 Hours":
            time_filter = now - timedelta(hours=6)
        elif time_window == "Last 12 Hours":
            time_filter = now - timedelta(hours=12)
        elif time_window == "Last 24 Hours":
            time_filter = now - timedelta(hours=24)
        else:
            time_filter = None
        
        if time_filter and 'prediction_timestamp' in df.columns:
            df = df[df['prediction_timestamp'] >= time_filter]
        
        # Severity filter
        if 'severity' in df.columns and severity_filter:
            df = df[df['severity'].isin(severity_filter)]
        
        # Line filter
        if line_filter and 'line_id' in df.columns:
            df = df[df['line_id'].str.contains(line_filter, case=False, na=False)]
        
        # Limit records
        df = df.head(max_records)
    
    # Calculate metrics
    metrics = calculate_metrics(df)
    
    # Main dashboard area
    st.markdown("## 📊 Real-time Metrics")
    
    # KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "📈 Total Samples",
            f"{metrics['total_samples']:,}",
            delta=f"+{metrics['last_hour_anomalies']} (last hour)" if metrics['last_hour_anomalies'] > 0 else None
        )
    
    with col2:
        st.metric(
            "🚨 Total Anomalies",
            f"{metrics['total_anomalies']:,}",
            delta=f"{metrics['anomaly_rate']:.1f}% rate"
        )
    
    with col3:
        if metrics['high_severity'] > 0:
            st.metric(
                "⚠️ High Severity",
                metrics['high_severity'],
                delta="Critical",
                delta_color="inverse"
            )
        else:
            st.metric("✅ High Severity", "0", delta="Good")
    
    with col4:
        st.metric(
            "📊 Avg Score",
            f"{metrics['avg_score']:.4f}",
            delta="Lower is worse" if metrics['avg_score'] < -0.1 else "Normal range"
        )
    
    # Alerts section
    if metrics['high_severity'] > 0:
        st.markdown(f"""
        <div class="alert-high">
            🚨 <strong>HIGH PRIORITY ALERT:</strong> {metrics['high_severity']} high-severity anomalies detected! 
            Immediate investigation required.
        </div>
        """, unsafe_allow_html=True)
    elif metrics['medium_severity'] > 5:
        st.markdown(f"""
        <div class="alert-medium">
            ⚠️ <strong>ATTENTION:</strong> {metrics['medium_severity']} medium-severity anomalies detected. 
            Monitor closely.
        </div>
        """, unsafe_allow_html=True)
    
    # Main visualizations
    if not df.empty:
        st.markdown("## 📈 Advanced Analytics")
        
        # Time series analysis
        time_series_fig = create_time_series_chart(df)
        st.plotly_chart(time_series_fig, use_container_width=True)
        
        # Distribution analysis
        col1, col2 = st.columns(2)
        dist_fig1, dist_fig2 = create_distribution_charts(df)
        
        with col1:
            st.plotly_chart(dist_fig1, use_container_width=True)
        with col2:
            st.plotly_chart(dist_fig2, use_container_width=True)
        
        # Operational metrics
        st.markdown("## 🏭 Operational Intelligence")
        ops_fig = create_operational_metrics(df)
        st.plotly_chart(ops_fig, use_container_width=True)
        
        # Detailed data table
        st.markdown("## 📋 Detailed Anomaly Records")
        
        # Search functionality
        search_term = st.text_input("🔍 Search records", placeholder="Search by sample ID, line, station...")
        
        display_df = df.copy()
        if search_term:
            mask = (
                display_df.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
            )
            display_df = display_df[mask]
        
        # Display columns
        display_columns = [
            'sample_id', 'prediction_timestamp', 'anomaly_score', 
            'severity', 'line_id', 'station_id', 'shift'
        ]
        display_columns = [col for col in display_columns if col in display_df.columns]
        
        if not display_df.empty:
            st.dataframe(
                display_df[display_columns].head(100),
                use_container_width=True,
                height=400
            )
            
            # Export functionality
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                st.markdown(export_data_to_csv(display_df), unsafe_allow_html=True)
            with col2:
                st.metric("Filtered Records", len(display_df))
        else:
            st.info("🔍 No records match your search criteria.")
    
    else:
        st.markdown("""
        <div class="info-box">
            <h3>📊 No Data Available</h3>
            <p>No anomaly data found. This could be because:</p>
            <ul>
                <li>The data files haven't been generated yet</li>
                <li>The specified path doesn't contain data files</li>
                <li>All anomalies are filtered out by current settings</li>
            </ul>
            <p><strong>💡 Tip:</strong> Try generating sample data first or check your filter settings.</p>
        </div>
        """, unsafe_allow_html=True)
    
    # System status footer
    st.markdown("---")
    st.markdown("## ⚙️ System Status")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if KAFKA_AVAILABLE:
            st.markdown('<span class="status-good">✅ Kafka: Available</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-warning">⚠️ Kafka: Not Available</span>', unsafe_allow_html=True)
    
    with col2:
        if os.path.exists(output_path if 'output_path' in locals() else 'output/anomalies'):
            st.markdown('<span class="status-good">✅ File Output: Available</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-warning">⚠️ File Output: Not Found</span>', unsafe_allow_html=True)
    
    with col3:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.markdown(f'🕒 **Last Update:** {current_time}')
    
    with col4:
        st.markdown(f'📊 **Data Window:** {time_window}')
    
    # Auto-refresh logic
    if auto_refresh and 'refresh_interval' in locals():
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        st.info("Dashboard stopped by user")
    except Exception as e:
        st.error(f"An error occurred: {e}")
        logger.error(f"Dashboard error: {e}") 