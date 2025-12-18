import streamlit as st
import random
import time
from database import db
from iot_api_client import get_iot_client

def get_user_hubs(user_email):
    """Lấy danh sách hub của user"""
    try:
        hubs = db.get("iot_hubs", {"user_email": user_email})
        return hubs if hubs else []
    except Exception:
        return []

def get_nodes_from_telemetry(hub_id):
    """
    Lấy danh sách nodes và các biến số từ bản ghi telemetry mới nhất.
    Trả về dict: { 'node_id': {'type': '...', 'variables': [...]} }
    """
    try:
        # Lấy telemetry của hub
        telemetry_list = db.get("telemetry", {"hub_id": hub_id})
        
        if not telemetry_list:
            return {}
            
        # Sắp xếp lấy bản ghi mới nhất
        # Giả sử format timestamp chuẩn ISO, sort string OK
        latest = sorted(telemetry_list, key=lambda x: x.get('timestamp', ''), reverse=True)[0]
        
        data = latest.get('data', {})
        nodes = {}
        
        # 1. Atmospheric Node
        atm = data.get('atmospheric_node')
        if atm and isinstance(atm, dict):
            n_id = atm.get('node_id')
            sensors = atm.get('sensors', {})
            if n_id:
                nodes[n_id] = {
                    'type': 'atmospheric',
                    'variables': list(sensors.keys())
                }
                
        # 2. Soil Nodes
        soil_nodes = data.get('soil_nodes', [])
        if isinstance(soil_nodes, list):
            for sn in soil_nodes:
                if isinstance(sn, dict):
                    n_id = sn.get('node_id')
                    sensors = sn.get('sensors', {})
                    if n_id:
                         nodes[n_id] = {
                            'type': 'soil',
                            'variables': list(sensors.keys())
                        }
        
        return nodes
    except Exception as e:
        print(f"Error fetching nodes from telemetry: {e}")
        return {}

def render_irrigation_control():
    st.set_page_config(page_title="Quản lý Tưới Tiêu", page_icon="💧")
    
    st.title("💧 Quản lý Tưới Tiêu Tự Động")
    st.markdown("Điều khiển các thiết bị tưới tiêu và cấu hình tự động hóa.")
    
    # 1. Initialize Mock Data (Fake Devices)
    if "irrigation_devices" not in st.session_state:
        st.session_state.irrigation_devices = [
            {
                "id": "dev_001",
                "name": "Van Tưới Khu Vực A",
                "type": "switch",
                "status": False,  # Off
                "mode": "manual", # manual or auto
                "config": {
                    "hub_id": None,
                    "sensor_id": None,
                    "variable": None,
                    "threshold": 40.0,
                    "condition": "below" # below or above
                }
            },
            {
                "id": "dev_002",
                "name": "Van Tưới Khu Vực B",
                "type": "switch",
                "status": False,
                "mode": "manual",
                "config": {
                    "hub_id": None,
                    "sensor_id": None,
                    "variable": None,
                    "threshold": 35.0,
                    "condition": "below"
                }
            },
            {
                "id": "dev_003",
                "name": "Máy Bơm Chính",
                "type": "switch",
                "status": False,
                "mode": "manual",
                "config": {
                    "hub_id": None,
                    "sensor_id": None,
                    "variable": None,
                    "threshold": 80.0,
                    "condition": "below"
                }
            }
        ]

    # Pretty names for variables
    variable_labels = {
        'soil_moisture': 'Độ ẩm đất (%)', 
        'soil_temperature': 'Nhiệt độ đất (°C)',
        'air_temperature': 'Nhiệt độ không khí (°C)',
        'air_humidity': 'Độ ẩm không khí (%)',
        'rain_intensity': 'Lượng mưa (mm/h)',
        'wind_speed': 'Tốc độ gió (m/s)',
        'light_intensity': 'Cường độ sáng (Lux)',
        'barometric_pressure': 'Áp suất khí quyển (hPa)'
    }

    # 2. Render Devices
    for index, device in enumerate(st.session_state.irrigation_devices):
        with st.container(border=True):
            col1, col2, col3 = st.columns([1, 2, 1])
            
            # Status Icon & Name
            with col1:
                status_color = "🟢" if device["status"] else "⚪"
                st.markdown(f"### {status_color}")
                st.caption("Trạng thái")
            
            with col2:
                st.subheader(device["name"])
                st.text(f"ID: {device['id']}")
                mode_label = "🤖 Tự động" if device["mode"] == "auto" else "🖐️ Thủ công"
                st.markdown(f"**Chế độ:** {mode_label}")

            # Control Switch (Manual)
            with col3:
                st.write("") # Spacer
                if device["mode"] == "manual":
                    # Toggle Button
                    new_status = st.toggle(
                        "Bật/Tắt", 
                        value=device["status"], 
                        key=f"toggle_{device['id']}"
                    )
                    if new_status != device["status"]:
                        device["status"] = new_status
                        st.session_state.irrigation_devices[index] = device
                        st.rerun()
                else:
                    st.info("Đang chạy tự động")

            # Automation Configuration (Expander)
            with st.expander("⚙️ Cấu hình Tự động hóa"):
                
                # Mode Selection
                is_auto = st.checkbox(
                    "Kích hoạt chế độ tự động", 
                    value=(device["mode"] == "auto"),
                    key=f"auto_mode_{device['id']}"
                )
                
                # Update Mode immediately
                if is_auto and device["mode"] != "auto":
                    device["mode"] = "auto"
                    st.session_state.irrigation_devices[index] = device
                    st.rerun()
                elif not is_auto and device["mode"] != "manual":
                    device["mode"] = "manual"
                    st.session_state.irrigation_devices[index] = device
                    st.rerun()

                if is_auto:
                    st.markdown("---")
                    st.write("**Điều kiện kích hoạt:**")
                    
                    # 1. Select Hub
                    user_hubs = get_user_hubs(st.user.email)
                    if not user_hubs:
                        st.warning("Bạn chưa có Hub nào. Vui lòng đăng ký Hub trước.")
                        continue
                        
                    hub_options = {h['hub_id']: h.get('name', h['hub_id']) for h in user_hubs}
                    
                    # Ensure current hub_id is valid
                    current_hub_id = device["config"].get("hub_id")
                    if current_hub_id not in hub_options:
                        current_hub_id = list(hub_options.keys())[0]
                    
                    selected_hub_id = st.selectbox(
                        "1. Chọn Hub",
                        options=list(hub_options.keys()),
                        format_func=lambda x: hub_options[x],
                        index=list(hub_options.keys()).index(current_hub_id),
                        key=f"hub_select_{device['id']}"
                    )
                    
                    # 2. Select Sensor (Node) from Telemetry
                    # This now queries the telemetry table dynamically
                    nodes_data = get_nodes_from_telemetry(selected_hub_id)
                    
                    if not nodes_data:
                         st.warning(f"Hub '{hub_options[selected_hub_id]}' chưa gửi dữ liệu telemetry nào.")
                    else:
                        # List node IDs
                        node_ids = list(nodes_data.keys())
                        
                        # Ensure current sensor_id is valid for this hub
                        current_sensor_id = device["config"].get("sensor_id")
                        if current_sensor_id not in node_ids:
                             current_sensor_id = node_ids[0]

                        selected_sensor_id = st.selectbox(
                            "2. Chọn Node cảm biến",
                            options=node_ids,
                            format_func=lambda x: f"{x} ({nodes_data[x]['type']})",
                            index=node_ids.index(current_sensor_id),
                            key=f"sensor_select_{device['id']}"
                        )
                        
                        # 3. Select Variable based on selected node
                        avail_vars = nodes_data[selected_sensor_id]['variables']
                        
                        if not avail_vars:
                            st.warning("Node này không có biến số nào.")
                        else:
                            current_var = device["config"].get("variable")
                            if current_var not in avail_vars:
                                current_var = avail_vars[0]
                                
                            selected_variable = st.selectbox(
                                "3. Chọn Loại biến số",
                                options=avail_vars,
                                format_func=lambda x: variable_labels.get(x, x),
                                index=avail_vars.index(current_var),
                                key=f"var_select_{device['id']}"
                            )

                            # 4. Threshold & Condition
                            c1, c2 = st.columns(2)
                            with c1:
                                 selected_condition = st.selectbox(
                                    "Điều kiện",
                                    options=["below", "above"],
                                    format_func=lambda x: "Nhỏ hơn (<)" if x == "below" else "Lớn hơn (>)",
                                    index=0 if device["config"].get("condition") == "below" else 1,
                                    key=f"cond_select_{device['id']}"
                                )
                            with c2:
                                threshold_val = st.number_input(
                                    "Giá trị ngưỡng",
                                    value=float(device["config"].get("threshold", 0.0)),
                                    step=1.0,
                                    key=f"threshold_{device['id']}"
                                )

                            # Save Config
                            if st.button("Lưu cấu hình", key=f"save_{device['id']}"):
                                device["config"]["hub_id"] = selected_hub_id
                                device["config"]["sensor_id"] = selected_sensor_id
                                device["config"]["variable"] = selected_variable
                                device["config"]["condition"] = selected_condition
                                device["config"]["threshold"] = threshold_val
                                
                                st.session_state.irrigation_devices[index] = device
                                st.success("✅ Đã lưu cấu hình!")
                                time.sleep(0.5)
                                st.rerun()
                            
                            # Logic Description
                            var_name = variable_labels.get(selected_variable, selected_variable)
                            cond_text = "<" if selected_condition == "below" else ">"
                            st.info(f"💡 Logic: Nếu **{var_name}** của **{selected_sensor_id}** {cond_text} **{threshold_val}**, thiết bị sẽ **BẬT**.")

if __name__ == "__main__":
    render_irrigation_control()
