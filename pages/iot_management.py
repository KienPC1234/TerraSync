"""
TerraSync IoT Management Page
Quản lý thiết bị IoT, hub và cảm biến
"""

import streamlit as st
import json
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any
# from api_placeholders import terrasync_apis # <- Đã xóa mock
from database import db # <- Vẫn giữ lại cho user/fields/settings
from iot_api_client import get_iot_client, test_iot_connection # <- Import client thật

# Import các thư viện plotting nếu chưa có
try:
    import pandas as pd
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError:
    st.error("Cần cài đặt: pip install pandas plotly")
    st.stop()


@st.cache_data(ttl=60) # Cache trong 60 giây
def get_user_hub_data(user_email: str) -> List[Dict[str, Any]]:
    """
    Lấy và lọc tất cả dữ liệu hub/status/sensor cho user hiện tại từ API.
    """
    client = get_iot_client()
    all_hub_statuses = client.get_all_hub_statuses()
    
    if not all_hub_statuses:
        return []
    
    # Lọc các hub thuộc về user này
    user_hubs = []
    for hub_status in all_hub_statuses:
        if hub_status.get('hub') and hub_status['hub'].get('user_email') == user_email:
            user_hubs.append(hub_status)
            
    return user_hubs


def render_iot_management():
    """Trang quản lý thiết bị IoT"""
    st.title("🔧 IoT Device Management")
    st.markdown("Quản lý hub chính, cảm biến và kết nối RF 433MHz")
    
    # Check IoT API connection
    if not test_iot_connection():
        st.error("❌ Không thể kết nối đến IoT API. Vui lòng kiểm tra server.")
        st.info(f"💡 Đảm bảo API server đang chạy tại: `{get_iot_client().base_url}`")
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

        # Lấy danh sách vườn của user (từ DB local của Streamlit)
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
                hub_data = {
                    "hub_id": hub_id,
                    "user_email": st.user.email,
                    "field_id": selected_field_id,
                    "name": hub_name if hub_name else f"Hub {hub_id[:8]}",
                    "location": None, # Thêm các trường Pydantic yêu cầu
                    "description": None
                }
                
                # Register with IoT API
                client = get_iot_client()
                success = client.register_hub(hub_data) 
                
                if success:
                    st.success(f"✅ Hub '{hub_id}' registered successfully!")
                    st.cache_data.clear() # Xóa cache để tải lại danh sách
                    st.rerun()
                else:
                    st.error(f"❌ Failed to register hub '{hub_id}'. It might already exist, or there was an API error.")

    
    # Danh sách hubs (Lấy từ API thay vì DB local)
    st.subheader("📋 Registered Hubs")
    user_hubs_data = get_user_hub_data(st.user.email)
    
    if not user_hubs_data:
        st.info("No hubs registered yet. Add your first hub above.")
        return
    
    for hub_status in user_hubs_data:
        hub = hub_status.get('hub', {})
        if not hub:
            continue
            
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.markdown(f"**{hub.get('name', 'Unnamed Hub')}**")
                field_name = "N/A"
                if hub.get('field_id'):
                    # Vẫn lấy tên field từ DB local
                    field_list = db.get("fields", {"id": hub.get('field_id')})
                    if field_list:
                        field_name = field_list[0].get("name", "N/A")
                st.caption(f"📍 Field: {field_name}")
                st.caption(f"🆔 Hub ID: `{hub.get('hub_id', 'N/A')}`")
            
            with col2:
                # API trả về 'last_data_time' đã tính toán
                last_data_time_str = hub_status.get("last_data_time")
                status = "⚪ Unknown"
                if last_data_time_str:
                    try:
                        last_seen = datetime.fromisoformat(last_data_time_str)
                        
                        if (datetime.now(timezone.utc) - last_seen).total_seconds() < 960: # 16 phút
                             status = "🟢 Online"
                        else:
                             status = "🔴 Offline"
                    except (ValueError, TypeError):
                        status = "⚪ Invalid time"

                st.markdown(f"Status: {status}")
                st.caption(f"Last data: {last_data_time_str[:19] if last_data_time_str else 'N/A'}")

            
            with col3:
                if st.button("⚙️", key=f"config_{hub['hub_id']}", help="Configure"):
                    st.session_state.selected_hub = hub
                
                # Nút xóa bị vô hiệu hóa vì API không có endpoint delete
                st.button("🗑️", key=f"delete_{hub['hub_id']}", help="Delete (Not implemented in API)", disabled=True)
                # if st.button("🗑️", key=f"delete_{hub['hub_id']}", help="Delete"):
                #     st.warning("Delete function is not supported by the API yet.")
                #     # db.delete("iot_hubs", {"hub_id": hub["hub_id"]}) # <- Lỗi logic
                #     # st.rerun()

def render_sensor_management():
    """
    Quản lý cảm biến (ĐÃ SỬA)
    Lấy danh sách sensor động từ gói telemetry mới nhất.
    """
    st.subheader("🌡️ Sensor Management")
    
    # 1. Chọn hub (Không thay đổi)
    try:
        user_hubs_data = get_user_hub_data(st.user.email)
    except Exception as e:
        st.error(f"Lỗi khi tải dữ liệu hub: {e}")
        return
        
    if not user_hubs_data:
        st.warning("Please register a hub first.")
        return
    
    hub_options = {h['hub']['hub_id']: h['hub'].get('name', h['hub']['hub_id']) for h in user_hubs_data}
    selected_hub_id = st.selectbox(
        "Select Hub",
        options=list(hub_options.keys()),
        format_func=lambda x: hub_options[x]
    )
    
    if selected_hub_id:
        # 2. Lấy thông tin hub đã chọn
        hub_info = next((h for h in user_hubs_data if h['hub']['hub_id'] == selected_hub_id), None)
        
        if not hub_info:
            st.error("Could not retrieve hub data.")
            return

        # 3. Phân tích `latest_telemetry` để tạo danh sách sensor
        latest_telemetry = hub_info.get('latest_telemetry')
        sensors_from_telemetry = []
        last_seen_time = "N/A"
        
        if latest_telemetry and latest_telemetry.get('data'):
            telemetry_data = latest_telemetry.get('data')
            
            # Lấy thời gian "last_seen" từ chính gói telemetry
            raw_time_str = latest_telemetry.get('timestamp')
            if raw_time_str:
                try:
                    last_seen_dt = datetime.fromisoformat(raw_time_str)
                    last_seen_time = last_seen_dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    last_seen_time = raw_time_str[:19] # Cắt ngắn nếu không parse được
            
            # 3.1. Thêm node khí quyển (nếu có)
            atm_node = telemetry_data.get('atmospheric_node')
            if atm_node and isinstance(atm_node, dict):
                atm_node['sensor_type'] = 'atmospheric' # Tự gán type
                sensors_from_telemetry.append(atm_node)
                
            # 3.2. Thêm các node đất (nếu có)
            soil_nodes = telemetry_data.get('soil_nodes', [])
            if isinstance(soil_nodes, list):
                for node in soil_nodes:
                    if isinstance(node, dict):
                        node['sensor_type'] = 'soil' # Tự gán type
                        sensors_from_telemetry.append(node)
        
        # 4. Hiển thị Metrics (dựa trên danh sách sensor vừa phân tích)
        total_sensors = len(sensors_from_telemetry)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Active Sensors", total_sensors)
        with col2:
            st.metric("Online", total_sensors) # Nếu nó có trong telemetry, nó đang online
        with col3:
            st.metric("Offline", 0) # Không thể biết sensor offline từ 1 gói telemetry

        # 5. Hiển thị danh sách chi tiết sensor
        st.subheader("📋 Sensor Details (from latest report)")
        if not sensors_from_telemetry:
            st.info("No sensor data has been reported from this hub yet.")
            return

        for sensor in sensors_from_telemetry:
            with st.container(border=True):
                # Chỉ 3 cột vì không còn nút "Configure"
                col1, col2, col3 = st.columns([2, 3, 2]) 
                
                sensor_type = sensor.get('sensor_type', 'unknown')
                sensor_data = sensor.get('sensors', {})
                
                with col1:
                    st.markdown(f"**{sensor.get('node_id', 'N/A')}**")
                    st.caption(f"Type: {sensor_type.title()}")
                
                with col2:
                    # Hiển thị DỮ LIỆU THẬT thay vì placeholder
                    if sensor_type == 'soil':
                        moisture = sensor_data.get('soil_moisture')
                        temp = sensor_data.get('soil_temperature')
                        st.markdown(f"💧 Moisture: **{moisture:.1f}%**" if moisture is not None else "...")
                        st.caption(f"🌡️ Temp: **{temp:.1f}°C**" if temp is not None else "...")
                    
                    elif sensor_type == 'atmospheric':
                        temp = sensor_data.get('air_temperature')
                        humidity = sensor_data.get('air_humidity')
                        wind = sensor_data.get('wind_speed')
                        st.markdown(f"🌡️ Air Temp: **{temp:.1f}°C**" if temp is not None else "...")
                        st.caption(f"💧 Humidity: **{humidity:.1f}%** | 💨 Wind: **{wind:.1f} m/s**" if humidity is not None and wind is not None else "...")
                    
                    else:
                        st.info("Unknown sensor type")
                
                with col3:
                    # Status động
                    st.markdown("🟢 **Online**")
                    st.caption(f"Last Seen: {last_seen_time}")


def render_realtime_data():
    """Dữ liệu thời gian thực"""
    st.subheader("📊 Real-time IoT Data")
    
    # Auto-refresh toggle
    auto_refresh = st.checkbox("🔄 Auto-refresh (30s)", value=True)
    
    if auto_refresh:
        if "last_refresh" not in st.session_state:
            st.session_state.last_refresh = datetime.now()
        
        if (datetime.now() - st.session_state.last_refresh).total_seconds() > 30:
            st.session_state.last_refresh = datetime.now()
            st.rerun()
    
    # Chọn hub để xem dữ liệu (từ cache)
    user_hubs_data = get_user_hub_data(st.user.email)
    if not user_hubs_data:
        st.warning("Please register a hub first.")
        return
    
    hub_options = {h['hub']['hub_id']: h['hub'].get('name', h['hub']['hub_id']) for h in user_hubs_data}
    selected_hub_id = st.selectbox(
        "Select Hub for Data",
        options=list(hub_options.keys()),
        format_func=lambda x: hub_options[x],
        key="realtime_hub_selector"
    )
    
    if selected_hub_id:
        client = get_iot_client()
        # API trả về bản ghi data (không phải wrapper APIResponse)
        latest_data = client.get_latest_data(selected_hub_id)

        if not latest_data:
            st.warning("No recent data available for this hub.")
            return

        # 'latest_data' LÀ bản ghi telemetry, 'data' nằm bên trong nó
        data = latest_data.get('data')
        
        if not data:
            st.error("Invalid data structure received from API.")
            return
            
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
        # API trả về đối tượng data chứa 'items'
        history_data = client.get_data_history(selected_hub_id, limit=24) 

        if history_data and history_data.get('items'):
            
            df = pd.DataFrame(history_data['items'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Extract nested data
            df['soil_moisture'] = df['data'].apply(lambda d: d['soil_nodes'][0]['sensors']['soil_moisture'] if d.get('soil_nodes') and d['soil_nodes'] else None)
            df['air_temperature'] = df['data'].apply(lambda d: d['atmospheric_node']['sensors']['air_temperature'] if d.get('atmospheric_node') else None)
            df['air_humidity'] = df['data'].apply(lambda d: d['atmospheric_node']['sensors']['air_humidity'] if d.get('atmospheric_node') else None)
            
            df = df.sort_values('timestamp')

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
    """Cài đặt IoT (Giữ nguyên, dùng DB local)"""
    st.subheader("⚙️ IoT Settings")
    
    # Tải cài đặt hiện có
    current_settings = db.get("iot_settings", {"user_email": st.user.email})
    if current_settings:
        current_settings = current_settings[0] # Lấy bản ghi đầu tiên
    else:
        current_settings = {}

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📡 RF Communication")
        
        rf_frequency = st.number_input("RF Frequency (MHz)", value=current_settings.get("rf_frequency", 433.92), min_value=400.0, max_value=500.0)
        rf_power = st.slider("RF Power (dBm)", min_value=0, max_value=20, value=current_settings.get("rf_power", 17))
        rf_channel = st.selectbox("Default RF Channel", options=list(range(1, 11)), index=current_settings.get("rf_channel", 1) - 1)
        
        st.info("📡 RF 433MHz với ăng ten 17dBi, khoảng cách tối đa ~1km")
        
        st.subheader("🔄 Node Communication")
        
        polling_interval = st.slider("Polling Interval (minutes)", min_value=5, max_value=30, value=current_settings.get("polling_interval", 10))
        node_timeout = st.slider("Node Timeout (seconds)", min_value=5, max_value=30, value=current_settings.get("node_timeout", 15))
        retry_attempts = st.slider("Retry Attempts", min_value=1, max_value=5, value=current_settings.get("retry_attempts", 3))
        
        st.info(f"Node chính gọi từng node con mỗi {polling_interval} phút")
    
    with col2:
        st.subheader("🔋 Power Management")
        
        low_battery_threshold = st.slider("Low Battery Alert (%)", min_value=10, max_value=30, value=current_settings.get("low_battery_threshold", 20))
        critical_battery_threshold = st.slider("Critical Battery Alert (%)", min_value=5, max_value=15, value=current_settings.get("critical_battery_threshold", 10))
        
        st.info("🔋 Node con: pin 1100mAh, dùng được ~1 tháng")
        
        st.subheader("😴 Sleep Mode")
        
        sleep_duration = st.slider("Sleep Duration (seconds)", min_value=3, max_value=10, value=current_settings.get("sleep_duration", 5))
        listen_duration = st.slider("Listen Duration (ms)", min_value=200, max_value=1000, value=current_settings.get("listen_duration", 500))
        
        st.info(f"Node con ngủ {sleep_duration}s, nghe {listen_duration}ms")
        
        st.subheader("🚨 Alert Settings")
        
        enable_alerts = st.checkbox("Enable Push Notifications", value=current_settings.get("enable_alerts", True))
        alert_email = st.text_input("Alert Email", value=current_settings.get("alert_email", st.user.email))
        
        if enable_alerts:
            st.success("✅ Alerts will be sent to your email")
        else:
            st.warning("⚠️ Alerts disabled")
    
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
        
        if current_settings:
            db.update("iot_settings", {"user_email": st.user.email}, settings)
        else:
            db.add("iot_settings", settings)
        
        st.success("✅ Settings saved successfully!")

def render_alerts():
    """Hiển thị alerts từ IoT API"""
    st.subheader("🚨 IoT Alerts")
    
    client = get_iot_client()
    user_hubs_data = get_user_hub_data(st.user.email)
    
    if not user_hubs_data:
        st.warning("No hubs registered. Please register a hub first.")
        return
    
    all_alerts = []
    for hub_status in user_hubs_data:
        hub_id = hub_status['hub'].get("hub_id")
        if hub_id:
            hub_alerts_response = client.get_alerts(hub_id, limit=20)
            if hub_alerts_response and hub_alerts_response.get('items'):
                all_alerts.extend(hub_alerts_response['items'])
    
    if not all_alerts:
        st.info("No alerts found. Your IoT system is running smoothly! 🎉")
        return
    
    all_alerts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    alert_level = st.selectbox("Filter by Level", ["All", "critical", "warning", "info"])
    if alert_level != "All":
        all_alerts = [alert for alert in all_alerts if alert.get("level") == alert_level]
    
    for alert in all_alerts[:10]:
        level = alert.get("level", "info")
        message = alert.get("message", "No message")
        created_at = alert.get("created_at", "Unknown time")
        hub_id = alert.get("hub_id", "Unknown hub")
        node_id = alert.get("node_id", "")
        
        if level == "critical":
            st.error(f"🚨 **CRITICAL** - {message}")
        elif level == "warning":
            st.warning(f"⚠️ **WARNING** - {message}")
        else:
            st.info(f"ℹ️ **INFO** - {message}")
        
        with st.expander(f"Details - {created_at[:16]}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Hub ID:** {hub_id}")
                st.write(f"**Node ID:** {node_id or 'N/A'}")
            with col2:
                st.write(f"**Level:** {level.upper()}")
                st.write(f"**Time:** {created_at}")
    
    if st.button("🗑️ Clear Old Alerts (older than 7 days)"):
        st.info("This feature is handled automatically by the API server.")

# -----
# Hàm render_iot_management() là hàm chính cần được gọi từ trang chính
# -----
# if __name__ == "__main__":
#     # Mock st.user.email để test
#     class MockUser:
#         email = "test@example.com"
#     st.user = MockUser()
#     render_iot_management()