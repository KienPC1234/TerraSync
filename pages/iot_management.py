"""
TerraSync IoT Management Page
Quản lý thiết bị IoT, hub và cảm biến
"""

import streamlit as st
import json
import random
from datetime import datetime, timedelta, timezone
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
        hub_id = st.text_input("Hub ID", placeholder="Enter the ID from your Hub device")
        hub_name = st.text_input("Hub Name (Optional)", placeholder="e.g., Main Farm Hub")

        # Lấy danh sách vườn của user
        user_fields = db.get("fields", {"user_email": st.user.email})
        if not user_fields:
            st.warning("You need to create a field first before adding a hub.")
            return

        field_options = {field['id']: field['name'] for field in user_fields}
        selected_field_id = st.selectbox("Choose a field to assign this hub to", options=list(field_options.keys()), format_func=lambda x: field_options[x])
        
        if st.button("🔗 Register Hub", type="primary"):
            if not hub_id:
                st.error("Hub ID is required.")
            elif not selected_field_id:
                st.error("You must select a field.")
            else:
                # Create hub data for IoT API
                hub_data = {
                    "hub_id": hub_id,
                    "user_email": st.user.email,
                    "field_id": selected_field_id,
                    "name": hub_name if hub_name else f"Hub {hub_id[:8]}"
                }
                
                # Register with IoT API
                client = get_iot_client()
                # The client's register_hub returns a boolean (True for success, False for failure)
                success = client.register_hub(hub_data) 
                
                if success:
                    st.success(f"✅ Hub '{hub_id}' registered successfully!")
                    st.rerun()
                else:
                    st.error(f"❌ Failed to register hub '{hub_id}'. It might already exist, or there was an API error.")

    
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
                field_name = "N/A"
                if hub.get('field_id'):
                    # Assuming db.get returns a list
                    field_list = db.get("fields", {"id": hub.get('field_id')})
                    if field_list:
                        field_name = field_list[0].get("name", "N/A")
                st.caption(f"📍 Field: {field_name}")
                st.caption(f"🆔 Hub ID: `{hub.get('hub_id', 'N/A')}`")
            
            with col2:
                # Status indicator based on last_seen
                last_seen_str = hub.get("last_seen")
                status = "⚪ Unknown"
                if last_seen_str:
                    try:
                        # Handle different ISO formats
                        if last_seen_str.endswith('Z'):
                            last_seen_str = last_seen_str.replace("Z", "+00:00")
                        
                        last_seen = datetime.fromisoformat(last_seen_str)
                        
                        # Make last_seen offset-aware if it's not
                        if last_seen.tzinfo is None:
                            last_seen = last_seen.replace(tzinfo=timezone.utc)

                        if (datetime.now(timezone.utc) - last_seen).total_seconds() < 960: # 16 minutes
                             status = "🟢 Online"
                        else:
                             status = "🔴 Offline"
                    except (ValueError, TypeError):
                        status = "⚪ Invalid time"

                st.markdown(f"Status: {status}")
                st.caption(f"Last seen: {hub.get('last_seen', 'N/A')[:19] if hub.get('last_seen') else 'N/A'}")

            
            with col3:
                if st.button("⚙️", key=f"config_{hub['hub_id']}", help="Configure"):
                    st.session_state.selected_hub = hub
                
                if st.button("🗑️", key=f"delete_{hub['hub_id']}", help="Delete"):
                    # In a real app, this should call an API to delete the hub
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
    
    hub_options = {hub['hub_id']: hub.get('name', hub['hub_id']) for hub in user_hubs}
    selected_hub_id = st.selectbox(
        "Select Hub",
        options=list(hub_options.keys()),
        format_func=lambda x: hub_options[x]
    )
    
    if selected_hub_id:
        # Lấy thông tin cảm biến từ API
        client = get_iot_client()
        # get_hub_status returns a list of hub statuses
        status_data_list = client.get_hub_status(selected_hub_id)
        
        if status_data_list:
            # Assuming we are interested in the first hub's status for the selected_hub_id
            hub_info = status_data_list[0]
            sensors = hub_info.get('sensors', [])
            
            # Thống kê tổng quan
            online_sensors = sum(1 for s in sensors if s.get('status') == 'active') # Assuming 'active' means online
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Sensors", len(sensors))
            with col2:
                st.metric("Online", online_sensors)
            with col3:
                st.metric("Offline", len(sensors) - online_sensors)

            # Danh sách cảm biến
            st.subheader("📋 Sensor Details")
            if not sensors:
                st.info("This hub has not reported any sensors yet.")

            for sensor in sensors:
                with st.container():
                    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                    
                    with col1:
                        st.markdown(f"**{sensor.get('node_id', 'N/A')}**")
                        st.caption(f"Type: {sensor.get('sensor_type', 'N/A').replace('_', ' ').title()}")
                    
                    with col2:
                        # Battery and signal are not in the current model, using placeholders
                        battery_level = random.randint(20, 100)
                        signal_strength = random.randint(40, 100)
                        battery_color = "🟢" if battery_level > 70 else "🟡" if battery_level > 30 else "🔴"
                        st.markdown(f"{battery_color} Battery: {battery_level}%")
                        
                        signal_color = "🟢" if signal_strength > 80 else "🟡" if signal_strength > 50 else "🔴"
                        st.caption(f"{signal_color} Signal: {signal_strength}%")
                    
                    with col3:
                        status = sensor.get('status', 'unknown')
                        status_color = "🟢" if status == "active" else "🔴"
                        st.markdown(f"{status_color} {status.title()}")
                        st.caption(f"Last seen: {sensor.get('last_seen', 'N/A')[:16]}")
                    
                    with col4:
                        if st.button("🔧", key=f"sensor_config_{sensor.get('node_id')}", help="Configure"):
                            st.session_state.selected_sensor = sensor
        else:
            st.error("Could not retrieve sensor data from the API.")


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
    
    hub_options = {hub['hub_id']: hub.get('name', hub['hub_id']) for hub in user_hubs}
    selected_hub_id = st.selectbox(
        "Select Hub for Data",
        options=list(hub_options.keys()),
        format_func=lambda x: hub_options[x],
        key="realtime_hub_selector"
    )
    
    if selected_hub_id:
        client = get_iot_client()
        latest_data = client.get_latest_data(selected_hub_id)

        if not latest_data or 'data' not in latest_data:
            st.warning("No recent data available for this hub.")
            return

        data = latest_data['data']
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🌡️ Soil Sensors")
            if 'soil_nodes' in data and data['soil_nodes']:
                for node in data['soil_nodes']:
                    st.metric(
                        f"Soil Moisture ({node.get('node_id')})",
                        f"{node['sensors']['soil_moisture']:.1f}%"
                    )
                    st.metric(
                        f"Soil Temperature ({node.get('node_id')})",
                        f"{node['sensors']['soil_temperature']:.1f}°C"
                    )
            else:
                st.info("No soil sensor data.")

        with col2:
            st.subheader("🌤️ Atmospheric Sensors")
            if 'atmospheric_node' in data:
                atm_sensors = data['atmospheric_node']['sensors']
                st.metric("Air Temperature", f"{atm_sensors['air_temperature']:.1f}°C")
                st.metric("Humidity", f"{atm_sensors['air_humidity']:.1f}%")
                st.metric("Wind Speed", f"{atm_sensors['wind_speed']:.1f} m/s")
            else:
                st.info("No atmospheric sensor data.")

        # Data visualization
        st.subheader("📈 Data Trends")
        history = client.get_data_history(selected_hub_id, limit=24) # Get last 24 records

        if history and history.get('items'):
            import pandas as pd
            
            df = pd.DataFrame(history['items'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Extract nested data
            df['soil_moisture'] = df['data'].apply(lambda d: d['soil_nodes'][0]['sensors']['soil_moisture'] if d.get('soil_nodes') else None)
            df['air_temperature'] = df['data'].apply(lambda d: d['atmospheric_node']['sensors']['air_temperature'] if d.get('atmospheric_node') else None)
            df['air_humidity'] = df['data'].apply(lambda d: d['atmospheric_node']['sensors']['air_humidity'] if d.get('atmospheric_node') else None)
            
            df = df.sort_values('timestamp')

            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            
            fig = make_subplots(
                rows=3, cols=1,
                subplot_titles=('Soil Moisture (%)', 'Air Temperature (°C)', 'Air Humidity (%)'),
                vertical_spacing=0.1,
                shared_xaxes=True
            )
            
            fig.add_trace(go.Scatter(x=df['timestamp'], y=df['soil_moisture'], name='Soil Moisture'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['timestamp'], y=df['air_temperature'], name='Air Temperature'), row=2, col=1)
            fig.add_trace(go.Scatter(x=df['timestamp'], y=df['air_humidity'], name='Air Humidity'), row=3, col=1)
            
            fig.update_layout(height=600, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough historical data to draw trends.")


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
            hub_alerts_response = client.get_alerts(hub_id, limit=20)
            if hub_alerts_response and hub_alerts_response.get('items'):
                all_alerts.extend(hub_alerts_response['items'])
    
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
