"""
TerraSync IoT Management Page
Quản lý thiết bị IoT, hub và cảm biến
"""

import streamlit as st
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any
from api_placeholders import terrasync_apis
from database import db
from iot_api_client import get_iot_client, test_iot_connection, get_iot_data_for_user, create_sample_telemetry_data, create_sample_hub_data, create_sample_sensor_data

def render_iot_management():
    """Trang quản lý thiết bị IoT"""
    st.title("🔧 IoT Device Management")
    st.markdown("Quản lý hub chính, cảm biến và kết nối RF 433MHz")
    
    # Check IoT API connection
    if not test_iot_connection():
        st.error("❌ Không thể kết nối đến IoT API. Vui lòng kiểm tra server.")
        st.info("💡 Để chạy IoT API: `cd iotAPI && ./run_api.sh`")
        return
    
    # Tabs cho các chức năng khác nhau
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📡 Hub Management", "🌡️ Sensors", "📊 Real-time Data", "🚨 Alerts", "⚙️ Settings"])
    
    with tab1:
        render_hub_management()
    
    with tab2:
        render_sensor_management()
    
    with tab3:
        render_realtime_data()
    
    with tab4:
        render_alerts()
    
    with tab5:
        render_iot_settings()

def render_hub_management():
    """Quản lý IoT Hub"""
    st.subheader("📡 IoT Hub Management")
    
    # Thêm hub mới
    with st.expander("➕ Add New Hub", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            hub_name = st.text_input("Hub Name", placeholder="Main Farm Hub")
            hub_location = st.text_input("Location", placeholder="Field A - North Section")
            hub_ip = st.text_input("Hub IP Address", placeholder="192.168.1.100")
        
        with col2:
            hub_lat = st.number_input("Latitude", value=20.450123, format="%.6f")
            hub_lon = st.number_input("Longitude", value=106.325678, format="%.6f")
            rf_channel = st.selectbox("RF Channel", options=list(range(1, 11)))
        
        if st.button("🔗 Register Hub", type="primary"):
            # Generate unique hub ID
            import uuid
            hub_id = f"hub-{uuid.uuid4().hex[:8]}"
            
            # Create hub data for IoT API
            hub_data = create_sample_hub_data(
                hub_id=hub_id,
                user_email=st.user.email,
                field_id="field-001",  # Default field
                lat=hub_lat,
                lon=hub_lon
            )
            
            # Register with IoT API
            client = get_iot_client()
            success = client.register_hub(hub_data)
            
            if success:
                # Also save to local database
                local_hub_data = {
                    "hub_id": hub_id,
                    "name": hub_name,
                    "location": hub_location,
                    "ip_address": hub_ip,
                    "coordinates": {"lat": hub_lat, "lon": hub_lon},
                    "rf_channel": rf_channel,
                    "user_email": st.user.email,
                    "registered_at": datetime.now().isoformat()
                }
                db.add("iot_hubs", local_hub_data)
                st.success(f"✅ Hub registered successfully! Hub ID: {hub_id}")
                st.rerun()
            else:
                st.error("❌ Failed to register hub with IoT API")
    
    # Danh sách hubs
    st.subheader("📋 Registered Hubs")
    user_hubs = db.get("iot_hubs", {"user_email": st.user.email})
    
    if not user_hubs:
        st.info("No hubs registered yet. Add your first hub above.")
        return
    
    for hub in user_hubs:
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.markdown(f"**{hub.get('name', 'Unnamed Hub')}**")
                st.caption(f"📍 {hub.get('location', 'Unknown location')}")
                st.caption(f"🆔 Hub ID: `{hub.get('hub_id', 'N/A')}`")
            
            with col2:
                # Status indicator
                status = "🟢 Online" if random.random() > 0.2 else "🔴 Offline"
                st.markdown(f"Status: {status}")
                st.caption(f"📡 RF Channel: {hub.get('rf_channel', 'N/A')}")
                st.caption(f"🌐 IP: {hub.get('ip_address', 'N/A')}")
            
            with col3:
                if st.button("⚙️", key=f"config_{hub['hub_id']}", help="Configure"):
                    st.session_state.selected_hub = hub
                
                if st.button("🗑️", key=f"delete_{hub['hub_id']}", help="Delete"):
                    db.delete("iot_hubs", {"hub_id": hub["hub_id"]})
                    st.rerun()

def render_sensor_management():
    """Quản lý cảm biến"""
    st.subheader("🌡️ Sensor Management")
    
    # Chọn hub để xem cảm biến
    user_hubs = db.get("iot_hubs", {"user_email": st.user.email})
    if not user_hubs:
        st.warning("Please register a hub first.")
        return
    
    selected_hub_id = st.selectbox(
        "Select Hub",
        options=[hub["hub_id"] for hub in user_hubs],
        format_func=lambda x: next(hub["name"] for hub in user_hubs if hub["hub_id"] == x)
    )
    
    if selected_hub_id:
        # Lấy thông tin cảm biến
        sensors_data = terrasync_apis.get_hub_sensors(selected_hub_id)
        
        if sensors_data["status"] == "success":
            sensors = sensors_data["sensors"]
            
            # Thống kê tổng quan
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Sensors", sensors_data["total_sensors"])
            with col2:
                st.metric("Online", sensors_data["online_sensors"])
            with col3:
                st.metric("Offline", sensors_data["total_sensors"] - sensors_data["online_sensors"])
            with col4:
                avg_battery = sum(s["battery_level"] for s in sensors) / len(sensors) if sensors else 0
                st.metric("Avg Battery", f"{avg_battery:.0f}%")
            
            # Danh sách cảm biến
            st.subheader("📋 Sensor Details")
            for sensor in sensors:
                with st.container():
                    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                    
                    with col1:
                        st.markdown(f"**{sensor['node_id']}**")
                        st.caption(f"Type: {sensor['type'].replace('_', ' ').title()}")
                    
                    with col2:
                        # Battery indicator
                        battery_color = "🟢" if sensor["battery_level"] > 70 else "🟡" if sensor["battery_level"] > 30 else "🔴"
                        st.markdown(f"{battery_color} Battery: {sensor['battery_level']}%")
                        
                        # Signal strength
                        signal_color = "🟢" if sensor["signal_strength"] > 80 else "🟡" if sensor["signal_strength"] > 50 else "🔴"
                        st.caption(f"{signal_color} Signal: {sensor['signal_strength']}%")
                    
                    with col3:
                        status_color = "🟢" if sensor["status"] == "online" else "🔴"
                        st.markdown(f"{status_color} {sensor['status'].title()}")
                        st.caption(f"Last seen: {sensor['last_seen'][:16]}")
                    
                    with col4:
                        if st.button("🔧", key=f"sensor_config_{sensor['node_id']}", help="Configure"):
                            st.session_state.selected_sensor = sensor

def render_realtime_data():
    """Dữ liệu thời gian thực"""
    st.subheader("📊 Real-time IoT Data")
    
    # Auto-refresh toggle
    auto_refresh = st.checkbox("🔄 Auto-refresh (30s)", value=True)
    
    if auto_refresh:
        # Auto-refresh every 30 seconds
        if "last_refresh" not in st.session_state:
            st.session_state.last_refresh = datetime.now()
        
        if (datetime.now() - st.session_state.last_refresh).total_seconds() > 30:
            st.session_state.last_refresh = datetime.now()
            st.rerun()
    
    # Chọn hub để xem dữ liệu
    user_hubs = db.get("iot_hubs", {"user_email": st.user.email})
    if not user_hubs:
        st.warning("Please register a hub first.")
        return
    
    selected_hub_id = st.selectbox(
        "Select Hub for Data",
        options=[hub["hub_id"] for hub in user_hubs],
        format_func=lambda x: next(hub["name"] for hub in user_hubs if hub["hub_id"] == x),
        key="realtime_hub_selector"
    )
    
    if selected_hub_id:
        # Simulate real-time data
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🌡️ Soil Sensors")
            
            # Soil moisture
            soil_moisture = random.uniform(20, 80)
            st.metric(
                "Soil Moisture",
                f"{soil_moisture:.1f}%",
                delta=f"{random.uniform(-5, 5):.1f}%"
            )
            
            # Soil temperature
            soil_temp = random.uniform(20, 35)
            st.metric(
                "Soil Temperature",
                f"{soil_temp:.1f}°C",
                delta=f"{random.uniform(-2, 2):.1f}°C"
            )
        
        with col2:
            st.subheader("🌤️ Atmospheric Sensors")
            
            # Air temperature
            air_temp = random.uniform(25, 40)
            st.metric(
                "Air Temperature",
                f"{air_temp:.1f}°C",
                delta=f"{random.uniform(-3, 3):.1f}°C"
            )
            
            # Humidity
            humidity = random.uniform(40, 90)
            st.metric(
                "Humidity",
                f"{humidity:.1f}%",
                delta=f"{random.uniform(-10, 10):.1f}%"
            )
            
            # Wind speed
            wind_speed = random.uniform(0, 15)
            st.metric(
                "Wind Speed",
                f"{wind_speed:.1f} m/s",
                delta=f"{random.uniform(-2, 2):.1f} m/s"
            )
        
        # Data visualization
        st.subheader("📈 Data Trends")
        
        # Generate sample time series data
        import pandas as pd
        import numpy as np
        
        time_range = pd.date_range(start=datetime.now() - timedelta(hours=24), 
                                 end=datetime.now(), freq='H')
        
        data = {
            'Time': time_range,
            'Soil Moisture': np.random.normal(50, 10, len(time_range)),
            'Temperature': np.random.normal(30, 5, len(time_range)),
            'Humidity': np.random.normal(70, 15, len(time_range))
        }
        
        df = pd.DataFrame(data)
        
        # Plot
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=('Soil Moisture (%)', 'Temperature (°C)', 'Humidity (%)'),
            vertical_spacing=0.1
        )
        
        fig.add_trace(
            go.Scatter(x=df['Time'], y=df['Soil Moisture'], name='Soil Moisture'),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(x=df['Time'], y=df['Temperature'], name='Temperature'),
            row=2, col=1
        )
        
        fig.add_trace(
            go.Scatter(x=df['Time'], y=df['Humidity'], name='Humidity'),
            row=3, col=1
        )
        
        fig.update_layout(height=600, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

def render_iot_settings():
    """Cài đặt IoT"""
    st.subheader("⚙️ IoT Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📡 RF Communication")
        
        # RF Settings
        rf_frequency = st.number_input("RF Frequency (MHz)", value=433.92, min_value=400.0, max_value=500.0)
        rf_power = st.slider("RF Power (dBm)", min_value=0, max_value=20, value=17)
        rf_channel = st.selectbox("Default RF Channel", options=list(range(1, 11)))
        
        st.info(f"📡 RF 433MHz với ăng ten 17dBi, khoảng cách tối đa ~1km")
        
        # Node communication settings
        st.subheader("🔄 Node Communication")
        
        polling_interval = st.slider("Polling Interval (minutes)", min_value=5, max_value=30, value=10)
        node_timeout = st.slider("Node Timeout (seconds)", min_value=5, max_value=30, value=15)
        retry_attempts = st.slider("Retry Attempts", min_value=1, max_value=5, value=3)
        
        st.info(f"Node chính gọi từng node con mỗi {polling_interval} phút")
    
    with col2:
        st.subheader("🔋 Power Management")
        
        # Battery settings
        low_battery_threshold = st.slider("Low Battery Alert (%)", min_value=10, max_value=30, value=20)
        critical_battery_threshold = st.slider("Critical Battery Alert (%)", min_value=5, max_value=15, value=10)
        
        st.info("🔋 Node con: pin 1100mAh, dùng được ~1 tháng")
        
        # Sleep mode settings
        st.subheader("😴 Sleep Mode")
        
        sleep_duration = st.slider("Sleep Duration (seconds)", min_value=3, max_value=10, value=5)
        listen_duration = st.slider("Listen Duration (ms)", min_value=200, max_value=1000, value=500)
        
        st.info(f"Node con ngủ {sleep_duration}s, nghe {listen_duration}ms")
        
        # Alert settings
        st.subheader("🚨 Alert Settings")
        
        enable_alerts = st.checkbox("Enable Push Notifications", value=True)
        alert_email = st.text_input("Alert Email", value=st.user.email)
        
        if enable_alerts:
            st.success("✅ Alerts will be sent to your email")
        else:
            st.warning("⚠️ Alerts disabled")
    
    # Save settings
    if st.button("💾 Save Settings", type="primary"):
        settings = {
            "rf_frequency": rf_frequency,
            "rf_power": rf_power,
            "rf_channel": rf_channel,
            "polling_interval": polling_interval,
            "node_timeout": node_timeout,
            "retry_attempts": retry_attempts,
            "low_battery_threshold": low_battery_threshold,
            "critical_battery_threshold": critical_battery_threshold,
            "sleep_duration": sleep_duration,
            "listen_duration": listen_duration,
            "enable_alerts": enable_alerts,
            "alert_email": alert_email,
            "user_email": st.user.email
        }
        
        # Update or create settings
        existing_settings = db.get("iot_settings", {"user_email": st.user.email})
        if existing_settings:
            db.update("iot_settings", {"user_email": st.user.email}, settings)
        else:
            db.add("iot_settings", settings)
        
        st.success("✅ Settings saved successfully!")

def render_alerts():
    """Hiển thị alerts từ IoT API"""
    st.subheader("🚨 IoT Alerts")
    
    # Get alerts from IoT API
    client = get_iot_client()
    user_hubs = db.get("iot_hubs", {"user_email": st.user.email})
    
    if not user_hubs:
        st.warning("No hubs registered. Please register a hub first.")
        return
    
    # Get alerts for all user hubs
    all_alerts = []
    for hub in user_hubs:
        hub_id = hub.get("hub_id")
        if hub_id:
            hub_alerts = client.get_alerts(hub_id, limit=20)
            all_alerts.extend(hub_alerts)
    
    if not all_alerts:
        st.info("No alerts found. Your IoT system is running smoothly! 🎉")
        return
    
    # Sort alerts by time (newest first)
    all_alerts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    # Filter by level
    alert_level = st.selectbox("Filter by Level", ["All", "critical", "warning", "info"])
    if alert_level != "All":
        all_alerts = [alert for alert in all_alerts if alert.get("level") == alert_level]
    
    # Display alerts
    for alert in all_alerts[:10]:  # Show latest 10 alerts
        level = alert.get("level", "info")
        message = alert.get("message", "No message")
        created_at = alert.get("created_at", "Unknown time")
        hub_id = alert.get("hub_id", "Unknown hub")
        node_id = alert.get("node_id", "")
        
        # Color coding
        if level == "critical":
            st.error(f"🚨 **CRITICAL** - {message}")
        elif level == "warning":
            st.warning(f"⚠️ **WARNING** - {message}")
        else:
            st.info(f"ℹ️ **INFO** - {message}")
        
        # Alert details
        with st.expander(f"Details - {created_at[:16]}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Hub ID:** {hub_id}")
                st.write(f"**Node ID:** {node_id or 'N/A'}")
            with col2:
                st.write(f"**Level:** {level.upper()}")
                st.write(f"**Time:** {created_at}")
    
    # Clear old alerts button
    if st.button("🗑️ Clear Old Alerts (older than 7 days)"):
        st.info("This feature will be implemented in future versions.")

# Import random for demo data
import random
