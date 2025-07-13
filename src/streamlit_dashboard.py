import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
import glob
from datetime import datetime, timedelta
import time
import joblib
from pathlib import Path

# Page configuration
st.set_page_config(
    page_title="Smart Manufacturing IoT - Anomaly Detection",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(90deg, #2E8B57 0%, #20B2AA 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .sub-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #2E8B57;
        margin-bottom: 1rem;
        border-left: 4px solid #20B2AA;
        padding-left: 1rem;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border: 1px solid #dee2e6;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s ease-in-out;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: #2E8B57;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    
    .metric-label {
        font-size: 1rem;
        color: #6c757d;
        text-align: center;
        font-weight: 500;
    }
    
    .status-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 8px;
    }
    
    .status-normal { background-color: #28a745; }
    .status-warning { background-color: #ffc107; }
    .status-critical { background-color: #dc3545; }
    
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
    }
    
    .stButton > button {
        background: linear-gradient(90deg, #2E8B57 0%, #20B2AA 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(46, 139, 87, 0.3);
    }
    
    .chart-container {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        margin-bottom: 1.5rem;
    }
    
    .info-box {
        background: linear-gradient(135deg, #e8f5e8 0%, #d4edda 100%);
        border: 1px solid #c3e6cb;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .warning-box {
        background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
        border: 1px solid #ffeaa7;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .critical-box {
        background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
        border: 1px solid #f5c6cb;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'anomaly_data' not in st.session_state:
    st.session_state.anomaly_data = pd.DataFrame()
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()

def load_anomaly_data():
    """Load anomaly data from JSON files"""
    all_data = []
    anomaly_files = glob.glob("output/anomalies/*-anomalies.json")
    
    for file in anomaly_files:
        try:
            with open(file, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        all_data.append(data)
        except Exception as e:
            st.error(f"Error reading {file}: {e}")
    
    if all_data:
        df = pd.DataFrame(all_data)
        df['timestamp'] = pd.to_datetime(df['sample_timestamp'])
        return df
    return pd.DataFrame()

def create_animated_gauge(value, title, min_val=0, max_val=100, color="#2E8B57"):
    """Create an animated gauge chart"""
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title, 'font': {'size': 20, 'color': '#2E8B57'}},
        delta={'reference': max_val * 0.8},
        gauge={
            'axis': {'range': [min_val, max_val], 'tickcolor': "#2E8B57"},
            'bar': {'color': color},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "#2E8B57",
            'steps': [
                {'range': [min_val, max_val * 0.6], 'color': "#e8f5e8"},
                {'range': [max_val * 0.6, max_val * 0.8], 'color': "#fff3cd"},
                {'range': [max_val * 0.8, max_val], 'color': "#f8d7da"}
            ],
            'threshold': {
                'line': {'color': "#dc3545", 'width': 4},
                'thickness': 0.75,
                'value': max_val * 0.9
            }
        }
    ))
    
    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
        font={'color': "#2E8B57", 'family': "Arial"},
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def create_3d_scatter(data):
    """Create a 3D scatter plot of anomalies"""
    if data.empty:
        return go.Figure()
    
    fig = go.Figure(data=[go.Scatter3d(
        x=data['anomaly_score'],
        y=data['timestamp'].dt.hour,
        z=data['timestamp'].dt.minute,
        mode='markers',
        marker=dict(
            size=8,
            color=data['anomaly_score'],
            colorscale='Greens',
            opacity=0.8
        ),
        text=data['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S'),
        hovertemplate='<b>Time:</b> %{text}<br>' +
                     '<b>Score:</b> %{x:.3f}<br>' +
                     '<b>Hour:</b> %{y}<br>' +
                     '<b>Minute:</b> %{z}<extra></extra>'
    )])
    
    fig.update_layout(
        title="3D Anomaly Distribution",
        scene=dict(
            xaxis_title="Anomaly Score",
            yaxis_title="Hour of Day",
            zaxis_title="Minute",
            bgcolor='rgba(0,0,0,0)'
        ),
        height=500,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def create_heatmap(data):
    """Create a heatmap of anomalies by hour and day"""
    if data.empty:
        return go.Figure()
    
    # Create pivot table for heatmap
    data['hour'] = data['timestamp'].dt.hour
    data['day'] = data['timestamp'].dt.day_name()
    
    heatmap_data = data.groupby(['day', 'hour']).size().unstack(fill_value=0)
    
    # Reorder days
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    heatmap_data = heatmap_data.reindex(day_order)
    
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data.values,
        x=heatmap_data.columns,
        y=heatmap_data.index,
        colorscale='Greens',
        hoverongaps=False
    ))
    
    fig.update_layout(
        title="Anomaly Heatmap by Day and Hour",
        xaxis_title="Hour of Day",
        yaxis_title="Day of Week",
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

def create_timeline_chart(data):
    """Create an interactive timeline chart"""
    if data.empty:
        return go.Figure()
    
    fig = go.Figure()
    
    # Normal data points
    normal_data = data[data['anomaly_score'] > -0.1]
    if not normal_data.empty:
        fig.add_trace(go.Scatter(
            x=normal_data['timestamp'],
            y=normal_data['anomaly_score'],
            mode='markers',
            name='Normal',
            marker=dict(color='#28a745', size=6, opacity=0.6),
            hovertemplate='<b>Time:</b> %{x}<br><b>Score:</b> %{y:.3f}<extra></extra>'
        ))
    
    # Anomaly data points
    anomaly_data = data[data['anomaly_score'] <= -0.1]
    if not anomaly_data.empty:
        fig.add_trace(go.Scatter(
            x=anomaly_data['timestamp'],
            y=anomaly_data['anomaly_score'],
            mode='markers',
            name='Anomaly',
            marker=dict(color='#dc3545', size=10, opacity=0.8),
            hovertemplate='<b>Time:</b> %{x}<br><b>Score:</b> %{y:.3f}<extra></extra>'
        ))
    
    fig.update_layout(
        title="Real-time Anomaly Timeline",
        xaxis_title="Time",
        yaxis_title="Anomaly Score",
        height=400,
        hovermode='closest',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig

def create_distribution_chart(data):
    """Create an interactive distribution chart"""
    if data.empty:
        return go.Figure()
    
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=data['anomaly_score'],
        nbinsx=30,
        name='Score Distribution',
        marker_color='#20B2AA',
        opacity=0.7
    ))
    
    fig.add_trace(go.Scatter(
        x=data['anomaly_score'],
        y=np.zeros_like(data['anomaly_score']),
        mode='markers',
        name='Individual Scores',
        marker=dict(color='#2E8B57', size=4, opacity=0.6),
        hovertemplate='<b>Score:</b> %{x:.3f}<extra></extra>'
    ))
    
    fig.update_layout(
        title="Anomaly Score Distribution",
        xaxis_title="Anomaly Score",
        yaxis_title="Frequency",
        height=400,
        barmode='overlay',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig

# Sidebar configuration
with st.sidebar:
    st.markdown("## Dashboard Controls")
    
    # Data source selection
    data_source = st.selectbox(
        "Data Source",
        ["File System", "Kafka Stream"],
        help="Choose where to load anomaly data from"
    )
    
    # Refresh settings
    refresh_interval = st.slider(
        "Refresh Interval (seconds)",
        min_value=5,
        max_value=60,
        value=30,
        help="How often to refresh the data"
    )
    
    # Auto-refresh toggle
    auto_refresh = st.checkbox(
        "Enable Auto-refresh",
        value=True,
        help="Automatically refresh data at specified interval"
    )
    
    # Manual refresh button
    if st.button("Refresh Now"):
        st.session_state.anomaly_data = load_anomaly_data()
        st.session_state.last_refresh = datetime.now()
        st.success("Data refreshed successfully!")
    
    # Filter options
    st.markdown("### Filters")
    
    # Severity filter
    severity_filter = st.multiselect(
        "Severity Level",
        ["LOW", "MEDIUM", "HIGH"],
        default=["LOW", "MEDIUM", "HIGH"],
        help="Filter by anomaly severity"
    )
    
    # Station filter
    station_filter = st.multiselect(
        "Manufacturing Station",
        ["All Stations"],
        default=["All Stations"],
        help="Filter by specific stations"
    )
    
    # Line filter
    line_filter = st.multiselect(
        "Production Line",
        ["All Lines"],
        default=["All Lines"],
        help="Filter by specific production lines"
    )
    
    # Date range filter
    st.markdown("### Date Range")
    date_range = st.date_input(
        "Select Date Range",
        value=(datetime.now().date() - timedelta(days=7), datetime.now().date()),
        help="Filter data by date range"
    )

# Main dashboard
st.markdown('<h1 class="main-header">Smart Manufacturing IoT - Anomaly Detection</h1>', unsafe_allow_html=True)

# Load data
if st.session_state.anomaly_data.empty:
    st.session_state.anomaly_data = load_anomaly_data()

# Auto-refresh logic
if auto_refresh:
    time_since_refresh = (datetime.now() - st.session_state.last_refresh).total_seconds()
    if time_since_refresh >= refresh_interval:
        st.session_state.anomaly_data = load_anomaly_data()
        st.session_state.last_refresh = datetime.now()

# Key metrics
st.markdown('<h2 class="sub-header">System Overview</h2>', unsafe_allow_html=True)

if not st.session_state.anomaly_data.empty:
    data = st.session_state.anomaly_data
    
    # Calculate metrics
    total_samples = len(data)
    anomaly_count = len(data[data['is_anomaly'] == True])
    anomaly_rate = (anomaly_count / total_samples * 100) if total_samples > 0 else 0
    
    # Recent activity (last 24 hours)
    recent_data = data[data['timestamp'] >= datetime.now() - timedelta(hours=24)]
    recent_anomalies = len(recent_data[recent_data['is_anomaly'] == True])
    
    # System health score (inverse of anomaly rate)
    system_health = max(0, 100 - anomaly_rate)
    
    # --- User Engagement: Trend Arrows ---
    prev_24h = data[(data['timestamp'] >= datetime.now() - timedelta(hours=48)) & (data['timestamp'] < datetime.now() - timedelta(hours=24))]
    prev_anomalies = len(prev_24h[prev_24h['is_anomaly'] == True])
    trend = "↑" if recent_anomalies > prev_anomalies else ("↓" if recent_anomalies < prev_anomalies else "→")
    trend_color = "#28a745" if recent_anomalies < prev_anomalies else ("#dc3545" if recent_anomalies > prev_anomalies else "#ffc107")
    
    # Display metrics in cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card" title="Total number of samples processed in the system.">
            <div class="metric-value">{total_samples:,}</div>
            <div class="metric-label">Total Samples Processed</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card" title="Number of samples detected as anomalies.">
            <div class="metric-value">{anomaly_count:,}</div>
            <div class="metric-label">Anomalies Detected</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card" title="Percentage of samples flagged as anomalies.">
            <div class="metric-value">{anomaly_rate:.1f}%</div>
            <div class="metric-label">Anomaly Rate</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card" title="Number of anomalies detected in the last 24 hours.">
            <div class="metric-value">{recent_anomalies} <span style='color:{trend_color};font-size:1.5rem;'>{trend}</span></div>
            <div class="metric-label">Recent Anomalies (24h)</div>
        </div>
        """, unsafe_allow_html=True)
    
    # --- User Engagement: Quick Filter Buttons ---
    st.markdown('<div style="margin:1rem 0;">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Show Only High Severity Anomalies"):
            st.session_state.anomaly_data = data[data['severity'] == 'HIGH']
    with col2:
        if st.button("Show Last 24h Only"):
            st.session_state.anomaly_data = data[data['timestamp'] >= datetime.now() - timedelta(hours=24)]
    with col3:
        if st.button("Reset Filters"):
            st.session_state.anomaly_data = load_anomaly_data()
    st.markdown('</div>', unsafe_allow_html=True)
    
    # --- Visualizations ---
    st.markdown('<h2 class="sub-header">Anomaly Analysis</h2>', unsafe_allow_html=True)
    
    # 3D Scatter Plot
    with st.container():
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown("### 3D Anomaly Distribution")
        scatter_3d = create_3d_scatter(data)
        st.plotly_chart(scatter_3d, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Timeline and Distribution
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown("### Real-time Timeline")
        timeline = create_timeline_chart(data)
        st.plotly_chart(timeline, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown("### Score Distribution")
        distribution = create_distribution_chart(data)
        st.plotly_chart(distribution, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Heatmap
    with st.container():
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown("### Anomaly Patterns by Time")
        heatmap = create_heatmap(data)
        st.plotly_chart(heatmap, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # --- System Health (moved after heatmap) ---
    st.markdown('<h2 class="sub-header">System Health</h2>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        health_gauge = create_animated_gauge(system_health, "System Health Score", color="#2E8B57")
        st.plotly_chart(health_gauge, use_container_width=True)
    
    # --- User Engagement: Insights Card ---
    st.markdown('<div class="info-box">', unsafe_allow_html=True)
    if anomaly_rate > 50:
        st.markdown("**Insight:** High anomaly rate detected. Consider investigating recent process changes or equipment status.")
    elif recent_anomalies > prev_anomalies:
        st.markdown("**Insight:** Anomaly count is increasing compared to the previous day. Monitor for potential issues.")
    elif recent_anomalies < prev_anomalies:
        st.markdown("**Insight:** Anomaly count is decreasing. System health is improving.")
    else:
        st.markdown("**Insight:** Anomaly rate is stable. Continue monitoring for changes.")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Detailed data table
    st.markdown('<h2 class="sub-header">Recent Anomalies</h2>', unsafe_allow_html=True)
    
    # Filter data based on sidebar selections
    filtered_data = data.copy()
    
    if severity_filter and "All" not in severity_filter:
        filtered_data = filtered_data[filtered_data['severity'].isin(severity_filter)]
    
    if station_filter and "All Stations" not in station_filter:
        filtered_data = filtered_data[filtered_data['station_id'].isin(station_filter)]
    
    if line_filter and "All Lines" not in line_filter:
        filtered_data = filtered_data[filtered_data['line_id'].isin(line_filter)]
    
    # Display recent anomalies
    recent_anomalies_data = filtered_data[filtered_data['is_anomaly'] == True].tail(20)
    
    if not recent_anomalies_data.empty:
        # Create a styled dataframe
        display_data = recent_anomalies_data[['timestamp', 'sample_id', 'severity', 'line_id', 'station_id', 'anomaly_score']].copy()
        display_data['timestamp'] = display_data['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        display_data['anomaly_score'] = display_data['anomaly_score'].round(3)
        
        # Apply styling
        def color_anomaly(val):
            if val == 'HIGH':
                return 'background-color: #f8d7da; color: #721c24;'
            elif val == 'MEDIUM':
                return 'background-color: #fff3cd; color: #856404;'
            else:
                return 'background-color: #d4edda; color: #155724;'
        
        styled_df = display_data.style.applymap(color_anomaly, subset=['severity'])
        st.dataframe(styled_df, use_container_width=True)
    else:
        st.info("No anomalies found with the current filters.")
    
    # Export functionality
    st.markdown('<h2 class="sub-header">Data Export</h2>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Export Anomaly Data"):
            csv = filtered_data.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"anomaly_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    with col2:
        if st.button("Export Summary Report"):
            # Create summary report
            summary = f"""
            Anomaly Detection Summary Report
            Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            Total Samples: {total_samples:,}
            Anomalies Detected: {anomaly_count:,}
            Anomaly Rate: {anomaly_rate:.2f}%
            System Health Score: {system_health:.1f}%
            
            Severity Breakdown:
            - High: {len(data[data['severity'] == 'HIGH'])}
            - Medium: {len(data[data['severity'] == 'MEDIUM'])}
            - Low: {len(data[data['severity'] == 'LOW'])}
            """
            st.download_button(
                label="Download Report",
                data=summary,
                file_name=f"anomaly_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )

else:
    st.warning("No anomaly data found. Please ensure data files are available in the output/anomalies/ directory.")
    
    # Show sample data structure
    st.markdown('<h2 class="sub-header">Expected Data Structure</h2>', unsafe_allow_html=True)
    st.info("""
    The dashboard expects JSON files in the output/anomalies/ directory with the following structure:
    - sample_timestamp: ISO timestamp
    - sample_id: Unique sample identifier
    - is_anomaly: Boolean indicating anomaly status
    - anomaly_score: Numerical anomaly score
    - severity: LOW, MEDIUM, or HIGH
    - line_id: Production line identifier
    - station_id: Manufacturing station identifier
    - shift: Day, Evening, or Night shift
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #6c757d; padding: 1rem;">
    Smart Manufacturing IoT Anomaly Detection Dashboard | 
    Real-time monitoring and analysis of manufacturing processes
</div>
""", unsafe_allow_html=True) 