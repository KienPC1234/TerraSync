# pages/my_schedule.py
import streamlit as st
import plotly.express as px
import pandas as pd
from database import db
from datetime import datetime, timedelta
import logging

# Import logic từ module tập trung
from untils.irrigation_logic import get_hub_id_for_field, get_latest_telemetry_stats, calculate_daily_water_needs

# Giả định: import hàm get_field_data từ my_fields để xóa cache
try:
    from .my_fields import get_field_data
except ImportError:
    # Fallback nếu không import được
    class MockGetFieldData:
        @staticmethod
        def clear():
            pass
    get_field_data = MockGetFieldData

logger = logging.getLogger(__name__)

# --- Hằng số cho logic tưới tiêu (có thể chỉnh) ---
MOISTURE_MIN_THRESHOLD = 25.0  # Dưới mức này là 'dehydrated'
MOISTURE_MAX_THRESHOLD = 55.0  # Trên mức này là 'hydrated'
RAIN_THRESHOLD_MMH = 1.0       # Mưa (mm/h) để coi là đang tưới

# ===================================================================
# --- HÀM HELPER ĐỂ LẤY DỮ LIỆU ---
# ===================================================================

@st.cache_data(ttl=300) # Cache 5 phút cho biểu đồ
def get_field_telemetry_history(user_email: str, field_id: str) -> pd.DataFrame:
    """
    Lấy LỊCH SỬ telemetry cho biểu đồ.
    Hàm này vẫn ở đây vì nó dùng decorator của Streamlit.
    """
    hub_id = get_hub_id_for_field(user_email, field_id)
    if not hub_id:
        return pd.DataFrame() 

    telemetry_data = db.get("telemetry", {"hub_id": hub_id})
    if not telemetry_data:
        return pd.DataFrame()
    
    records = []
    for entry in telemetry_data:
        timestamp = entry.get("timestamp")
        data = entry.get("data", {})
        
        # Lấy soil moisture (tính trung bình nếu có nhiều node)
        nodes = data.get("soil_nodes", [])
        if nodes:
            values = [n['sensors']['soil_moisture'] for n in nodes if n.get('sensors') and 'soil_moisture' in n['sensors']]
            if values:
                avg_moisture = sum(values) / len(values)
                records.append({
                    "timestamp": timestamp,
                    "Metric": "Soil Moisture (Avg)",
                    "Value": avg_moisture
                })

        # Lấy air temperature
        atm_node = data.get("atmospheric_node", {})
        if atm_node.get('sensors') and 'air_temperature' in atm_node['sensors']:
            records.append({
                "timestamp": timestamp,
                "Metric": "Air Temperature",
                "Value": atm_node['sensors']['air_temperature']
            })
            
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.sort_values(by="timestamp")


# ===================================================================
# --- HÀM RENDER CHÍNH ---
# ===================================================================

def render_schedule():
    st.title("📅 Irrigation Status & Planning")
    st.markdown("Quản lý lịch tưới và trạng thái tưới tiêu.")
    
    if not (hasattr(st, 'user') and st.user.email):
        st.error("Vui lòng đăng nhập để xem.")
        return
        
    user_fields = db.get("fields", {"user_email": st.user.email})
    
    if not user_fields:
        st.warning("Không tìm thấy vườn. Vui lòng thêm vườn (field) trước.")
        return

    # --- NÚT TÍNH TOÁN ---
    st.subheader("🚀 Daily Irrigation Calculation")
    st.markdown("Nhấn nút này vào đầu mỗi ngày để tính toán lượng nước tưới khuyến nghị cho tất cả các vườn dựa trên thông số cây trồng và diện tích.")
    if st.button("Tính toán nhu cầu tưới hôm nay cho tất cả các vườn", type="primary"):
        with st.spinner("Đang tính toán..."):
            updated_count = 0
            for field in user_fields:
                try:
                    # Gọi hàm tính toán cốt lõi
                    water_needs = calculate_daily_water_needs(field)
                    
                    # Cập nhật DB với schema mới
                    update_data = {
                        "base_today_water": water_needs["today_water"],
                        "base_time_needed": water_needs["time_needed"],
                        "today_water": water_needs["today_water"], # Ban đầu, nước cần tưới = base
                        "time_needed": water_needs["time_needed"], # Ban đầu, thời gian = base
                        "progress": 0, # Reset lại tiến độ
                        "status": "dehydrated" if water_needs["today_water"] > 0 else "hydrated"
                    }
                    if db.update_user_field(field.get('id'), st.user.email, update_data):
                        updated_count += 1
                except Exception as e:
                    logger.error(f"Lỗi khi tính toán cho field {field.get('id')}: {e}")
            
            st.success(f"✅ Hoàn tất! Đã tính toán và cập nhật {updated_count}/{len(user_fields)} vườn.")
            # Xóa cache để các trang khác load lại dữ liệu mới
            get_field_data.clear()
            st.rerun()

    # --- Giao diện chọn Vườn và Tabs ---
    field_options = {f"{field.get('name', 'Unnamed')} ({field.get('crop', 'Unknown')})": field for field in user_fields}
    selected_field_name = st.selectbox("Chọn Vườn để xem chi tiết", options=list(field_options.keys()))
    selected_field = field_options[selected_field_name]
    
    # Tabs
    tab1, tab2 = st.tabs(["📊 Trạng thái hiện tại", "⚙️ Cài đặt tưới"])
    
    with tab1:
        render_current_status(selected_field, user_fields)
    
    with tab2:
        render_schedule_settings(selected_field)

# ===================================================================
# --- TAB 1: TRẠNG THÁI HIỆN TẠI (ĐÃ SỬA) ---
# ===================================================================
def render_current_status(field, all_fields):
    """
    Hiển thị trạng thái tưới tiêu, ưu tiên dữ liệu LIVE từ cảm biến.
    """
    st.subheader(f"📊 Trạng thái hiện tại: {field.get('name')}")
    
    # Nút cập nhật
    if st.button("🔄 Cập nhật từ cảm biến"):
        get_field_telemetry_history.clear() # Xóa cache biểu đồ
        # Không cần xóa cache cho get_latest_telemetry_stats vì nó không cache
        st.rerun()

    # --- LẤY DỮ LIỆU LIVE ---
    live_stats = get_latest_telemetry_stats(field.get('user_email'), field.get('id'))
    
    # --- LẤY DỮ LIỆU TĨNH TỪ DB (để dự phòng) ---
    db_status = field.get('status', 'hydrated')
    db_today_water = field.get('today_water', 0)
    db_time_needed = field.get('time_needed', 0)
    db_progress = field.get('progress', 0)

    # --- KHAI BÁO BIẾN HIỂN THỊ ---
    display_status = db_status
    display_water = db_today_water
    display_time = db_time_needed
    display_progress = db_progress
    
    status_colors = {
        'hydrated': '#28a745', # Xanh lá
        'dehydrated': '#ffc107', # Vàng
        'severely_dehydrated': '#dc3545' # Đỏ
    }

    # --- TÍNH TOÁN DYNAMC NẾU CÓ DỮ LIỆU LIVE ---
    if live_stats and live_stats.get("avg_moisture") is not None:
        avg_moisture = live_stats["avg_moisture"]
        rain_intensity = live_stats["rain_intensity"]
        
        # Lấy giá trị base để tính toán
        base_water = field.get('base_today_water', db_today_water)
        base_time = field.get('base_time_needed', db_time_needed)

        if rain_intensity > RAIN_THRESHOLD_MMH:
            display_status = "hydrated"
            display_progress = 100
            display_water = 0
            display_time = 0
            st.info(f"💧 Cảm biến phát hiện mưa ({rain_intensity} mm/h). Tự động ngưng tưới.")
        
        elif avg_moisture < MOISTURE_MIN_THRESHOLD:
            display_status = "dehydrated"
            display_progress = 0 
            display_water = base_water # Cần tưới toàn bộ
            display_time = base_time
            st.warning(f" Sensors detect low moisture: {avg_moisture:.1f}%.")

        elif avg_moisture > MOISTURE_MAX_THRESHOLD:
            display_status = "hydrated"
            display_progress = 100
            display_water = 0
            display_time = 0
            
        else: # Độ ẩm trong ngưỡng OK (ví dụ: 25% - 75%)
            display_status = "hydrated"
            # Logic mới: Tiến độ dựa trên độ ẩm hiện tại so với ngưỡng tối đa
            display_progress = int((avg_moisture / MOISTURE_MAX_THRESHOLD) * 100)
            display_progress = max(0, min(100, display_progress)) # Đảm bảo trong khoảng 0-100
            
            # Tính toán lượng nước/thời gian còn lại (tỷ lệ nghịch với tiến độ)
            remaining_factor = 1.0 - (display_progress / 100.0)
            display_water = round(base_water * remaining_factor, 1)
            display_time = round(base_time * remaining_factor, 1)

        try:
            ts = datetime.fromisoformat(live_stats['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
            st.caption(f"Trạng thái live tính toán từ cảm biến (lúc {ts})")
        except:
            st.caption(f"Trạng thái live tính toán từ cảm biến.")

    else:
        st.error("Không tìm thấy dữ liệu cảm biến (Hub/Sensor offline?). Hiển thị dữ liệu đã lưu cuối cùng.")
    
    # --- Hiển thị các chỉ số (Metrics) ---
    st.markdown(f"**Trạng thái tưới:** <span style='color:{status_colors.get(display_status, '#6c757d')}; font-weight:bold;'>{display_status.title().replace('_', ' ')}</span>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Water Needed Today", f"{display_water} m³")
    with col2:
        st.metric("Time Needed", f"{display_time} hours")
    with col3:
        st.metric("Progress", f"{display_progress}%")
    
    st.progress(display_progress, text=f"Watering Progress: {display_progress}%")

    # --- Chi tiết vườn (Field Details) ---
    st.subheader("📋 Field Details")
    col_a, col_b = st.columns(2)
    with col_a:
        st.write(f"**Crop:** {field.get('crop', 'N/A')}")
        st.write(f"**Stage:** {field.get('stage', 'N/A')}")
    with col_b:
        st.write(f"**Area:** {field.get('area', 0):.2f} ha")
        st.write(f"**Days to Harvest:** {field.get('days_to_harvest', 'N/A')}")

    st.divider()

    # --- Biểu đồ tổng quan (Giữ nguyên) ---
    st.subheader("📈 Tổng quan Nhu cầu tưới (Tất cả các vườn)")
    
    if all_fields:
        water_data = []
        for f in all_fields:
            # Dùng dữ liệu tĩnh từ DB cho biểu đồ tổng quan
            water_data.append({
                "Vườn": f.get('name', 'N/A'),
                "Lượng nước (m³)": f.get('today_water', 0),
                "Thời gian (giờ)": f.get('time_needed', 0)
            })
        df_water = pd.DataFrame(water_data)
        
        if df_water["Lượng nước (m³)"].sum() > 0:
            fig = px.bar(df_water, 
                         x='Vườn', 
                         y='Lượng nước (m³)', 
                         title='Lượng nước cần tưới hôm nay (m³)',
                         hover_data=['Thời gian (giờ)'],
                         color='Lượng nước (m³)',
                         labels={'Vườn': 'Tên Vườn'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tất cả các vườn đều đã được tưới hôm nay.")

# ===================================================================
# --- TAB 2: CÀI ĐẶT (Giữ nguyên) ---
# ===================================================================
def render_schedule_settings(field):
    """Schedule settings and optimization"""
    st.subheader("⚙️ Schedule Settings & Optimization")
    
    # Current field settings
    st.write("**Current Field Settings:**")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Crop Type", field.get('crop', 'Unknown'))
        st.metric("Growth Stage", field.get('stage', 'Unknown'))
        st.metric("Area", f"{field.get('area', 0):.2f} hectares")
    
    with col2:
        st.metric("Crop Coefficient", field.get('crop_coefficient', 1.0))
        st.metric("Irrigation Efficiency", f"{field.get('irrigation_efficiency', 85)}%")
        st.metric("Current Status", field.get('status', 'Unknown'))
    
    # Optimization settings
    st.subheader("🔧 Optimization Settings")
    
    with st.form("optimization_settings"):
        col1, col2 = st.columns(2)
        
        with col1:
            target_efficiency = st.slider("Target Irrigation Efficiency (%)", 70, 95, field.get('irrigation_efficiency', 85))
            water_saving_mode = st.checkbox("Water Saving Mode", value=False)
            weather_adjustment = st.checkbox("Auto Weather Adjustment", value=True)
        
        with col2:
            irrigation_frequency = st.selectbox("Irrigation Frequency", ["Daily", "Every 2 days", "Every 3 days", "Weekly"])
            preferred_time = st.selectbox("Preferred Irrigation Time", ["Early Morning (6-8 AM)", "Evening (6-8 PM)", "Flexible"])
            max_duration = st.number_input("Max Irrigation Duration (hours)", 1, 12, 4)
        
        if st.form_submit_button("💾 Save Settings", type="primary"):
            update_data = {
                'irrigation_efficiency': target_efficiency,
                'water_saving_mode': water_saving_mode,
                'weather_adjustment': weather_adjustment,
                'irrigation_frequency': irrigation_frequency,
                'preferred_time': preferred_time,
                'max_duration': max_duration
            }
            
            try:
                if db.update_user_field(field.get('id'), field.get('user_email'), update_data):
                    st.success("✅ Settings saved successfully!")
                    get_field_data.clear() 
                    st.rerun()
                else:
                    st.error("Lỗi: Không thể lưu cài đặt.")
            except Exception as e:
                st.error(f"Lỗi khi lưu: {e}")

    
    # Sensor Data History
    st.subheader("📊 Sensor Data History (Chart)")
    
    # Dùng hàm cache cho biểu đồ
    telemetry_df = get_field_telemetry_history(st.user.email, field.get('id', ''))
    
    if not telemetry_df.empty:
        fig = px.line(
            telemetry_df,
            x='timestamp',
            y='Value',
            color='Metric',
            title=f"Sensor History for {field.get('name')}",
            labels={'timestamp': 'Date', 'Value': 'Sensor Value'}
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.write("**Recent Statistics:**")
        col1, col2 = st.columns(2)
        with col1:
            soil_data = telemetry_df[telemetry_df['Metric'] == 'Soil Moisture (Avg)']['Value']
            st.metric("Avg Soil Moisture", f"{soil_data.mean():.1f}%" if not soil_data.empty else "N/A")
        with col2:
            temp_data = telemetry_df[telemetry_df['Metric'] == 'Air Temperature']['Value']
            st.metric("Avg Air Temp", f"{temp_data.mean():.1f}°C" if not temp_data.empty else "N/A")
    else:
        st.info(f"No telemetry data found for this field. Ensure a Hub is assigned to field '{field.get('name')}' and is sending data.")