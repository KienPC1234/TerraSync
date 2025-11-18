import streamlit as st
import json
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from database import db
from iot_api_client import get_iot_client, test_iot_connection

try:
    import pandas as pd
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError:
    st.error("Cần cài đặt: pip install pandas plotly")
    st.stop()

@st.cache_data(ttl=60)
def get_user_hub_data(user_email: str) -> List[Dict[str, Any]]:
    try:
        client = get_iot_client()
        all_hub_statuses = client.get_all_hub_statuses()
        
        if not all_hub_statuses:
            return []
        
        user_hubs = []
        for hub_status in all_hub_statuses:
            hub = hub_status.get('hub')
            if isinstance(hub, dict) and hub.get('user_email') == user_email:
                user_hubs.append(hub_status)
                
        return user_hubs
    except Exception as e:
        st.error(f"Lỗi khi lấy dữ liệu hub: {e}")
        return []

def render_iot_management():
    st.title("🔧 Quản lý Thiết bị IoT")
    st.markdown("Quản lý hub chính, cảm biến và kết nối RF 433MHz")
    
    if not test_iot_connection():
        st.error("❌ Không thể kết nối đến IoT API. Vui lòng kiểm tra server.")
        st.info(f"💡 Đảm bảo API server đang chạy tại: `{get_iot_client().base_url}`")
        return
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📡 Quản lý Hub", "🌡️ Cảm biến", "📊 Dữ liệu thời gian thực", "🚨 Cảnh báo", "⚙️ Cài đặt"])
    
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

@st.dialog("Chỉnh sửa cấu hình Hub", width="medium")
def edit_hub_dialog(hub_id: str):
    st.subheader(f"Chỉnh sửa Hub (ID: {hub_id})")
    
    try:
        user_email = st.user.email
        hub_db = db.get("iot_hubs", {"hub_id": hub_id, "user_email": user_email})
        current_hub = hub_db[0] if hub_db else {}
    except Exception:
        current_hub = {}
    
    hub_name_edit = st.text_input("Tên Hub", value=current_hub.get('name', ''))
    description_edit = st.text_area("Mô tả", value=current_hub.get('description', ''), height=100)
    
    try:
        user_fields = db.get("fields", {"user_email": st.user.email})
        field_options = {field['id']: field['name'] for field in user_fields if 'id' in field and 'name' in field}
        if not field_options:
            st.warning("Không có vườn nào. Vui lòng tạo vườn trước.")
            return
    except Exception:
        field_options = {}
        st.error("Lỗi khi tải danh sách vườn.")
        return
    
    current_field_id = current_hub.get('field_id')
    available_field_ids = list(field_options.keys())
    if current_field_id and current_field_id in available_field_ids:
        selected_field_id_edit = st.selectbox(
            "Gán cho vườn", 
            options=available_field_ids, 
            format_func=lambda x: field_options[x],
            index=available_field_ids.index(current_field_id)
        )
    else:
        selected_field_id_edit = st.selectbox(
            "Gán cho vườn", 
            options=available_field_ids, 
            format_func=lambda x: field_options[x],
            index=0
        )
    
    location = current_hub.get('location', {})
    if not isinstance(location, dict):
        location = {}
    location_lat = st.number_input("Vĩ độ", value=location.get('lat', 0.0))
    location_lon = st.number_input("Kinh độ", value=location.get('lon', 0.0))
    
    if st.button("💾 Cập nhật Hub", type="primary"):
        updated_data = {
            "id": current_hub.get('id'),
            "hub_id": hub_id,
            "user_email": st.user.email,
            "name": hub_name_edit,
            "description": description_edit,
            "field_id": selected_field_id_edit,
            "location": {"lat": location_lat, "lon": location_lon} if location_lat != 0.0 or location_lon != 0.0 else None,
            "status": current_hub.get('status', 'active'),
            "registered_at": current_hub.get('registered_at'),
            "last_seen": current_hub.get('last_seen'),
            "created_at": current_hub.get('created_at')
        }
        
        try:
            client = get_iot_client()
            api_success = False
            if hasattr(client, 'update_hub'):
                api_success = client.update_hub(updated_data)
            if not api_success:
                if 'id' in current_hub:
                    db.update("iot_hubs", {"hub_id": hub_id, "user_email": updated_data['user_email']}, updated_data)
                else:
                    db.add("iot_hubs", updated_data)
            st.success("✅ Cập nhật hub thành công!")
        except Exception as e:
            st.error(f"Lỗi khi cập nhật hub: {e}")
        
        st.cache_data.clear()
        st.rerun()
    
    if st.button("❌ Hủy"):
        st.rerun()

@st.dialog("Xác nhận xóa Hub", width="small")
def delete_hub_dialog(hub_id: str, hub_name: str):
    st.warning(f"Bạn có chắc chắn muốn xóa hub '{hub_name}' (ID: {hub_id}) không?")
    st.info("Hành động này không thể hoàn tác và sẽ xóa tất cả dữ liệu liên quan.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Có, xóa", type="primary", use_container_width=True):
            try:
                client = get_iot_client()
                api_success = False
                if hasattr(client, 'delete_hub'):
                    api_success = client.delete_hub(hub_id)
                if not api_success:
                    db.delete("iot_hubs", {"hub_id": hub_id, "user_email": st.user.email})
                st.success("✅ Xóa hub thành công!")
            except Exception as e:
                st.error(f"Lỗi khi xóa hub: {e}")
            
            st.cache_data.clear()
            st.rerun()
    
    with col2:
        if st.button("❌ Không, hủy", use_container_width=True):
            st.rerun()

def render_hub_management():
    st.subheader("📡 Quản lý Hub IoT")
    
    with st.expander("➕ Thêm Hub mới", expanded=False):
        hub_id = st.text_input("ID Hub", placeholder="Nhập ID từ thiết bị Hub của bạn")
        hub_name = st.text_input("Tên Hub (Tùy chọn)", placeholder="ví dụ: Hub chính")

        try:
            user_fields = db.get("fields", {"user_email": st.user.email})
            if not user_fields:
                st.warning("Bạn cần tạo một vườn trước khi thêm hub.")
                return
            field_options = {field['id']: field['name'] for field in user_fields if 'id' in field and 'name' in field}
            selected_field_id = st.selectbox("Chọn một vườn để gán hub này", options=list(field_options.keys()), format_func=lambda x: field_options[x])
        except Exception as e:
            st.error(f"Lỗi khi tải danh sách vườn: {e}")
            return
        
        if st.button("🔗 Đăng ký Hub", type="primary"):
            if not hub_id:
                st.error("Yêu cầu ID Hub.")
            elif not selected_field_id:
                st.error("Bạn phải chọn một vườn.")
            else:
                hub_data = {
                    "hub_id": hub_id,
                    "user_email": st.user.email,
                    "field_id": selected_field_id,
                    "name": hub_name if hub_name else f"Hub {hub_id[:8]}",
                    "location": None,
                    "description": None
                }
                
                try:
                    client = get_iot_client()
                    success = client.register_hub(hub_data) 
                    
                    if success:
                        st.success(f"✅ Đăng ký hub '{hub_id}' thành công!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"❌ Không thể đăng ký hub '{hub_id}'. Hub có thể đã tồn tại hoặc có lỗi API.")
                except Exception as e:
                    st.error(f"Lỗi API: {e}")
    
    st.subheader("📋 Các Hub đã đăng ký")
    user_hubs_data = get_user_hub_data(st.user.email)
    
    if not user_hubs_data:
        st.info("Chưa có hub nào được đăng ký. Thêm hub đầu tiên của bạn ở trên.")
        return
    
    for hub_status in user_hubs_data:
        hub = hub_status.get('hub')
        if not isinstance(hub, dict):
            continue
            
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.markdown(f"**{hub.get('name', 'Hub không tên')}**")
                field_name = "N/A"
                field_id = hub.get('field_id')
                if field_id:
                    try:
                        field_list = db.get("fields", {"id": field_id})
                        if field_list:
                            field_name = field_list[0].get("name", "N/A")
                    except Exception:
                        field_name = "Lỗi tải vườn"
                st.caption(f"📍 Vườn: {field_name}")
                st.caption(f"🆔 ID Hub: `{hub.get('hub_id', 'N/A')}`")
            
            with col2:
                last_data_time_str = hub_status.get("last_data_time")
                status = "⚪ Không xác định"
                if last_data_time_str:
                    try:
                        last_seen = datetime.fromisoformat(last_data_time_str.replace('Z', '+00:00'))
                        
                        if (datetime.now(timezone.utc) - last_seen).total_seconds() < 960:
                             status = "🟢 Online"
                        else:
                             status = "🔴 Offline"
                    except (ValueError, TypeError):
                        status = "⚪ Thời gian không hợp lệ"

                st.markdown(f"Trạng thái: {status}")
                st.caption(f"Dữ liệu cuối: {last_data_time_str[:19] if last_data_time_str else 'N/A'}")

            
            with col3:
                if st.button("⚙️", key=f"config_{hub['hub_id']}", help="Cấu hình"):
                    edit_hub_dialog(hub['hub_id'])
                
                if st.button("🗑️", key=f"delete_{hub['hub_id']}", help="Xóa Hub"):
                    delete_hub_dialog(hub['hub_id'], hub.get('name', 'Hub không tên'))

def render_sensor_management():
    st.subheader("🌡️ Quản lý cảm biến")
    
    try:
        user_hubs_data = get_user_hub_data(st.user.email)
    except Exception as e:
        st.error(f"Lỗi khi tải dữ liệu hub: {e}")
        return
        
    if not user_hubs_data:
        st.warning("Vui lòng đăng ký hub trước.")
        return
    
    hub_options = {}
    for h in user_hubs_data:
        hub_dict = h.get('hub', {})
        if isinstance(hub_dict, dict):
            hub_id = hub_dict.get('hub_id')
            hub_name = hub_dict.get('name', hub_id)
            if hub_id:
                hub_options[hub_id] = hub_name
    
    if not hub_options:
        st.warning("Không tìm thấy hub hợp lệ.")
        return
    
    selected_hub_id = st.selectbox(
        "Chọn Hub",
        options=list(hub_options.keys()),
        format_func=lambda x: hub_options[x]
    )
    
    if selected_hub_id:
        hub_info = next((h for h in user_hubs_data if h.get('hub', {}).get('hub_id') == selected_hub_id), None)
        
        if not hub_info:
            st.error("Không thể lấy dữ liệu hub.")
            return

        latest_telemetry = hub_info.get('latest_telemetry')
        sensors_from_telemetry = []
        last_seen_time = "N/A"
        
        if latest_telemetry and latest_telemetry.get('data'):
            telemetry_data = latest_telemetry.get('data')
            
            raw_time_str = latest_telemetry.get('timestamp')
            if raw_time_str:
                try:
                    last_seen_dt = datetime.fromisoformat(raw_time_str.replace('Z', '+00:00'))
                    last_seen_time = last_seen_dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    last_seen_time = raw_time_str[:19]
            
            atm_node = telemetry_data.get('atmospheric_node')
            if isinstance(atm_node, dict):
                atm_node['sensor_type'] = 'atmospheric'
                sensors_from_telemetry.append(atm_node)
                
            soil_nodes = telemetry_data.get('soil_nodes', [])
            if isinstance(soil_nodes, list):
                for node in soil_nodes:
                    if isinstance(node, dict):
                        node['sensor_type'] = 'soil'
                        sensors_from_telemetry.append(node)
        
        total_sensors = len(sensors_from_telemetry)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Tổng số cảm biến đang hoạt động", total_sensors)
        with col2:
            st.metric("Online", total_sensors)
        with col3:
            st.metric("Offline", 0)

        st.subheader("📋 Chi tiết cảm biến (từ báo cáo mới nhất)")
        if not sensors_from_telemetry:
            st.info("Chưa có dữ liệu cảm biến nào được báo cáo từ hub này.")
            return

        for sensor in sensors_from_telemetry:
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 3, 2]) 
                
                sensor_type = sensor.get('sensor_type', 'không xác định')
                sensor_data = sensor.get('sensors', {})
                if not isinstance(sensor_data, dict):
                    sensor_data = {}
                
                with col1:
                    st.markdown(f"**{sensor.get('node_id', 'N/A')}**")
                    st.caption(f"Loại: {sensor_type.title()}")
                
                with col2:
                    if sensor_type == 'soil':
                        moisture = sensor_data.get('soil_moisture')
                        temp = sensor_data.get('soil_temperature')
                        st.markdown(f"💧 Độ ẩm: **{moisture:.1f}%**" if isinstance(moisture, (int, float)) else "💧 Độ ẩm: ...")
                        st.caption(f"🌡️ Nhiệt độ: **{temp:.1f}°C**" if isinstance(temp, (int, float)) else "🌡️ Nhiệt độ: ...")
                    
                    elif sensor_type == 'atmospheric':
                        temp = sensor_data.get('air_temperature')
                        humidity = sensor_data.get('air_humidity')
                        wind = sensor_data.get('wind_speed')
                        st.markdown(f"🌡️ Nhiệt độ không khí: **{temp:.1f}°C**" if isinstance(temp, (int, float)) else "🌡️ Nhiệt độ không khí: ...")
                        st.caption(f"💧 Độ ẩm: **{humidity:.1f}%** | 💨 Gió: **{wind:.1f} m/s**" if isinstance(humidity, (int, float)) and isinstance(wind, (int, float)) else "💧 Độ ẩm/Gió: ...")
                    
                    else:
                        st.info("Loại cảm biến không xác định")
                
                with col3:
                    st.markdown("🟢 **Online**")
                    st.caption(f"Lần cuối thấy: {last_seen_time}")

def render_realtime_data():
    st.subheader("📊 Dữ liệu IoT thời gian thực")
    
    auto_refresh = st.checkbox("🔄 Tự động làm mới (30s)", value=True)
    
    if auto_refresh:
        if "last_refresh" not in st.session_state:
            st.session_state.last_refresh = datetime.now()
        
        if (datetime.now() - st.session_state.last_refresh).total_seconds() > 30:
            st.session_state.last_refresh = datetime.now()
            st.rerun()
    
    user_hubs_data = get_user_hub_data(st.user.email)
    if not user_hubs_data:
        st.warning("Vui lòng đăng ký hub trước.")
        return
    
    hub_options = {}
    for h in user_hubs_data:
        hub_dict = h.get('hub', {})
        if isinstance(hub_dict, dict):
            hub_id = hub_dict.get('hub_id')
            hub_name = hub_dict.get('name', hub_id)
            if hub_id:
                hub_options[hub_id] = hub_name
    
    selected_hub_id = st.selectbox(
        "Chọn Hub để xem dữ liệu",
        options=list(hub_options.keys()),
        format_func=lambda x: hub_options[x],
        key="realtime_hub_selector"
    )
    
    if selected_hub_id:
        try:
            client = get_iot_client()
            latest_data = client.get_latest_data(selected_hub_id)

            if not latest_data:
                st.warning("Không có dữ liệu gần đây cho hub này.")
                return

            data = latest_data.get('data')
            
            if not data or not isinstance(data, dict):
                st.error("Cấu trúc dữ liệu không hợp lệ nhận được từ API.")
                return
                
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🌡️ Cảm biến đất")
                soil_nodes = data.get('soil_nodes', [])
                if isinstance(soil_nodes, list) and soil_nodes:
                    for node in soil_nodes:
                        if isinstance(node, dict):
                            sensors = node.get('sensors', {})
                            if isinstance(sensors, dict):
                                moisture = sensors.get('soil_moisture')
                                temp = sensors.get('soil_temperature')
                                node_id = node.get('node_id', 'Không xác định')
                                st.metric(f"Độ ẩm đất ({node_id})", f"{moisture:.1f}%" if isinstance(moisture, (int, float)) else "N/A")
                                st.metric(f"Nhiệt độ đất ({node_id})", f"{temp:.1f}°C" if isinstance(temp, (int, float)) else "N/A")
                else:
                    st.info("Không có dữ liệu cảm biến đất.")

            with col2:
                st.subheader("🌤️ Cảm biến khí quyển")
                atm_node = data.get('atmospheric_node')
                if isinstance(atm_node, dict):
                    atm_sensors = atm_node.get('sensors', {})
                    if isinstance(atm_sensors, dict):
                        temp = atm_sensors.get('air_temperature')
                        humidity = atm_sensors.get('air_humidity')
                        wind = atm_sensors.get('wind_speed')
                        st.metric("Nhiệt độ không khí", f"{temp:.1f}°C" if isinstance(temp, (int, float)) else "N/A")
                        st.metric("Độ ẩm", f"{humidity:.1f}%" if isinstance(humidity, (int, float)) else "N/A")
                        st.metric("Tốc độ gió", f"{wind:.1f} m/s" if isinstance(wind, (int, float)) else "N/A")
                else:
                    st.info("Không có dữ liệu cảm biến khí quyển.")

            st.subheader("📈 Xu hướng dữ liệu")
            history_data = client.get_data_history(selected_hub_id, limit=24) 

            if history_data and history_data.get('items') and isinstance(history_data['items'], list):
                
                df = pd.DataFrame(history_data['items'])
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
                
                def extract_soil_moisture(d):
                    if isinstance(d, dict) and 'soil_nodes' in d and d['soil_nodes']:
                        nodes = d['soil_nodes']
                        if isinstance(nodes, list) and len(nodes) > 0:
                            first_node = nodes[0]
                            if isinstance(first_node, dict) and 'sensors' in first_node:
                                return first_node['sensors'].get('soil_moisture')
                    return None
                
                def extract_atm_temp(d):
                    if isinstance(d, dict) and 'atmospheric_node' in d:
                        atm = d['atmospheric_node']
                        if isinstance(atm, dict) and 'sensors' in atm:
                            return atm['sensors'].get('air_temperature')
                    return None
                
                def extract_atm_hum(d):
                    if isinstance(d, dict) and 'atmospheric_node' in d:
                        atm = d['atmospheric_node']
                        if isinstance(atm, dict) and 'sensors' in atm:
                            return atm['sensors'].get('air_humidity')
                    return None
                
                df['soil_moisture'] = df['data'].apply(extract_soil_moisture)
                df['air_temperature'] = df['data'].apply(extract_atm_temp)
                df['air_humidity'] = df['data'].apply(extract_atm_hum)
                
                df = df.dropna(subset=['timestamp']).sort_values('timestamp')

                if len(df) > 0:
                    fig = make_subplots(rows=3, cols=1, subplot_titles=('Độ ẩm đất (%)', 'Nhiệt độ không khí (°C)', 'Độ ẩm không khí (%)'), vertical_spacing=0.1, shared_xaxes=True)
                    
                    if 'soil_moisture' in df and not df['soil_moisture'].isna().all():
                        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['soil_moisture'], name='Độ ẩm đất'), row=1, col=1)
                    if 'air_temperature' in df and not df['air_temperature'].isna().all():
                        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['air_temperature'], name='Nhiệt độ không khí'), row=2, col=1)
                    if 'air_humidity' in df and not df['air_humidity'].isna().all():
                        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['air_humidity'], name='Độ ẩm không khí'), row=3, col=1)
                    
                    fig.update_layout(height=600, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Không có dữ liệu lịch sử hợp lệ để vẽ biểu đồ.")
            else:
                st.info("Không đủ dữ liệu lịch sử để vẽ xu hướng.")
        except Exception as e:
            st.error(f"Lỗi khi tải dữ liệu thời gian thực: {e}")

def render_iot_settings():
    st.subheader("⚙️ Cài đặt IoT")
    
    try:
        current_settings = db.get("iot_settings", {"user_email": st.user.email})
        if current_settings:
            current_settings = current_settings[0]
        else:
            current_settings = {}
    except Exception:
        current_settings = {}

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📡 Giao tiếp RF")
        rf_frequency = st.number_input("Tần số RF (MHz)", value=current_settings.get("rf_frequency", 433.92), min_value=400.0, max_value=500.0)
        rf_power = st.slider("Công suất RF (dBm)", min_value=0, max_value=20, value=current_settings.get("rf_power", 17))
        rf_channel = st.selectbox("Kênh RF mặc định", options=list(range(1, 11)), index=current_settings.get("rf_channel", 1) - 1 if current_settings.get("rf_channel") else 0)
        st.info("📡 RF 433MHz với ăng ten 17dBi, khoảng cách tối đa ~1km")
        
        st.subheader("🔄 Giao tiếp Node")
        polling_interval = st.slider("Khoảng thời gian lấy mẫu (phút)", min_value=5, max_value=30, value=current_settings.get("polling_interval", 10))
        node_timeout = st.slider("Thời gian chờ Node (giây)", min_value=5, max_value=30, value=current_settings.get("node_timeout", 15))
        retry_attempts = st.slider("Số lần thử lại", min_value=1, max_value=5, value=current_settings.get("retry_attempts", 3))
        st.info(f"Node chính gọi từng node con mỗi {polling_interval} phút")
    
    with col2:
        st.subheader("🔋 Quản lý năng lượng")
        low_battery_threshold = st.slider("Cảnh báo pin yếu (%)", min_value=10, max_value=30, value=current_settings.get("low_battery_threshold", 20))
        critical_battery_threshold = st.slider("Cảnh báo pin rất yếu (%)", min_value=5, max_value=15, value=current_settings.get("critical_battery_threshold", 10))
        st.info("🔋 Node con: pin 1100mAh, dùng được ~1 tháng")
        
        st.subheader("😴 Chế độ ngủ")
        sleep_duration = st.slider("Thời gian ngủ (giây)", min_value=3, max_value=10, value=current_settings.get("sleep_duration", 5))
        listen_duration = st.slider("Thời gian nghe (ms)", min_value=200, max_value=1000, value=current_settings.get("listen_duration", 500))
        st.info(f"Node con ngủ {sleep_duration}s, nghe {listen_duration}ms")
        
        st.subheader("🚨 Cài đặt cảnh báo")
        enable_alerts = st.checkbox("Bật thông báo đẩy", value=current_settings.get("enable_alerts", True))
        alert_email = st.text_input("Email cảnh báo", value=current_settings.get("alert_email", st.user.email))
        
        if enable_alerts:
            st.success("✅ Cảnh báo sẽ được gửi đến email của bạn")
        else:
            st.warning("⚠️ Cảnh báo đã tắt")
    
    if st.button("💾 Lưu cài đặt", type="primary"):
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
        
        try:
            if current_settings:
                db.update("iot_settings", {"user_email": st.user.email}, settings)
            else:
                db.add("iot_settings", settings)
            st.success("✅ Đã lưu cài đặt!")
        except Exception as e:
            st.error(f"Lỗi khi lưu cài đặt: {e}")

def render_alerts():
    st.subheader("🚨 Cảnh báo IoT")
    
    try:
        client = get_iot_client()
        user_hubs_data = get_user_hub_data(st.user.email)
    except Exception as e:
        st.error(f"Lỗi khi tải cảnh báo: {e}")
        return
    
    if not user_hubs_data:
        st.warning("Chưa có hub nào được đăng ký. Vui lòng đăng ký hub trước.")
        return
    
    all_alerts = []
    for hub_status in user_hubs_data:
        hub = hub_status.get('hub', {})
        hub_id = hub.get("hub_id")
        if hub_id:
            try:
                hub_alerts_response = client.get_alerts(hub_id, limit=20)
                if hub_alerts_response and hub_alerts_response.get('items') and isinstance(hub_alerts_response['items'], list):
                    all_alerts.extend(hub_alerts_response['items'])
            except Exception:
                continue
    
    if not all_alerts:
        st.info("Không tìm thấy cảnh báo nào. Hệ thống IoT của bạn đang hoạt động trơn tru! 🎉")
        return
    
    all_alerts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    alert_level = st.selectbox("Lọc theo mức độ", ["Tất cả", "critical", "warning", "info"])
    if alert_level != "Tất cả":
        all_alerts = [alert for alert in all_alerts if alert.get("level") == alert_level]
    
    for alert in all_alerts[:10]:
        if not isinstance(alert, dict):
            continue
        level = alert.get("level", "info")
        message = alert.get("message", "Không có tin nhắn")
        created_at = alert.get("created_at", "Thời gian không xác định")
        hub_id = alert.get("hub_id", "Hub không xác định")
        node_id = alert.get("node_id", "")
        
        if level == "critical":
            st.error(f"🚨 **CRITICAL** - {message}")
        elif level == "warning":
            st.warning(f"⚠️ **CẢNH BÁO** - {message}")
        else:
            st.info(f"ℹ️ **THÔNG TIN** - {message}")
        
        with st.expander(f"Chi tiết - {created_at[:16] if created_at != 'Thời gian không xác định' else 'Không xác định'}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**ID Hub:** {hub_id}")
                st.write(f"**ID Node:** {node_id or 'N/A'}")
            with col2:
                st.write(f"**Mức độ:** {level.upper()}")
                st.write(f"**Thời gian:** {created_at}")
    
    if st.button("🗑️ Xóa các cảnh báo cũ (hơn 7 ngày)"):
        st.info("Tính năng này được xử lý tự động bởi máy chủ API.")