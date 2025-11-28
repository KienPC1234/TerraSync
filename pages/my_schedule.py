import streamlit as st
import plotly.express as px
import pandas as pd
from database import db
from datetime import datetime, timedelta
import logging
import toml
from pathlib import Path
import numpy as np
from sklearn.linear_model import LinearRegression
from utils import get_latest_telemetry_stats, predict_water_needs, calculate_days_to_harvest
import requests
import math

logger = logging.getLogger(__name__)

# ===== Các hàm phụ để tính toán ET0 (FAO Penman-Monteith) =====
def saturation_vapor_pressure(T):
    # e_s (kPa)
    return 0.6108 * math.exp((17.27 * T) / (T + 237.3))

def slope_vapor_pressure_curve(T):
    # Δ (kPa/°C)
    e_s = saturation_vapor_pressure(T)
    return 4098 * e_s / ((T + 237.3) ** 2)

def psychrometric_constant(P=101.3):
    # γ (kPa/°C), P ~ 101.3 kPa ở mực nước biển
    return 0.000665 * P

def et0_FAO(T, RH, u2, Rs, P=101.3):
    # T: °C, RH: %, u2: m/s, Rs: MJ/m²/day
    e_s = saturation_vapor_pressure(T)
    e_a = e_s * RH / 100.0
    Δ = slope_vapor_pressure_curve(T)
    γ = psychrometric_constant(P)
    Rn = Rs  # giả sử G ≈ 0
    G = 0

    num = 0.408 * Δ * (Rn - G) + γ * (900 / (T + 273)) * u2 * (e_s - e_a)
    den = Δ + γ * (1 + 0.34 * u2)
    return num / den

def get_nasa_weather_data(lat, lon):
    # Lấy dữ liệu 30 ngày gần nhất
    end_date = datetime.now() - timedelta(days=2) # NASA data thường trễ 1-2 ngày
    start_date = end_date - timedelta(days=30)
    
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    url = (
        f"https://power.larc.nasa.gov/api/temporal/daily/point"
        f"?parameters=T2M,WS2M,RH2M,ALLSKY_SFC_SW_DWN"
        f"&community=AG"
        f"&longitude={lon}"
        f"&latitude={lat}"
        f"&start={start_str}"
        f"&end={end_str}"
        f"&format=JSON"
    )
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Error fetching NASA data: {e}")
    return None

def render_nasa_info(field):
    with st.expander("🌍 Dữ liệu Thời tiết & ET0 từ NASA (AOI)", expanded=False):
        st.caption("Dữ liệu từ NASA POWER Project (độ trễ 1-2 ngày). Tính toán ET0 theo chuẩn FAO-56 Penman-Monteith.")
        
        center = field.get('center', [21.0278, 105.8342]) # Default Hanoi if missing
        if not center or len(center) < 2:
             center = [21.0278, 105.8342]
        
        lat, lon = center[0], center[1]
        st.write(f"**Tọa độ:** Lat {lat:.4f}, Lon {lon:.4f}")

        if st.button("🔄 Tải dữ liệu NASA mới nhất"):
            with st.spinner("Đang kết nối tới NASA POWER API..."):
                data = get_nasa_weather_data(lat, lon)
                
                if data:
                    try:
                        params = data["properties"]["parameter"]
                        T2M = params.get("T2M", {})
                        WS2M = params.get("WS2M", {})
                        RH2M = params.get("RH2M", {})
                        RS = params.get("ALLSKY_SFC_SW_DWN", {})
                        
                        # Tính ET0
                        records = []
                        for day_str in T2M.keys():
                            try:
                                T = T2M[day_str]
                                RH = RH2M[day_str]
                                u2 = WS2M[day_str]
                                Rs = RS[day_str]
                                
                                # Kiểm tra dữ liệu hợp lệ (NASA đôi khi trả về -999)
                                if T > -90 and RH >= 0 and u2 >= 0 and Rs >= 0:
                                    et0 = round(et0_FAO(T, RH, u2, Rs), 2)
                                    
                                    date_obj = datetime.strptime(day_str, "%Y%m%d")
                                    records.append({
                                        "Ngày": date_obj,
                                        "Nhiệt độ (°C)": T,
                                        "Độ ẩm (%)": RH,
                                        "Gió (m/s)": u2,
                                        "Bức xạ (MJ/m²)": Rs,
                                        "ET0 (mm/ngày)": et0
                                    })
                            except Exception as e:
                                continue
                                
                        if records:
                            df_nasa = pd.DataFrame(records)
                            df_nasa = df_nasa.sort_values(by="Ngày", ascending=False)
                            
                            st.dataframe(df_nasa.style.format({
                                "Ngày": "{:%Y-%m-%d}",
                                "Nhiệt độ (°C)": "{:.1f}",
                                "Độ ẩm (%)": "{:.1f}",
                                "Gió (m/s)": "{:.1f}",
                                "Bức xạ (MJ/m²)": "{:.2f}",
                                "ET0 (mm/ngày)": "{:.2f}"
                            }))
                            
                            # Biểu đồ ET0
                            fig = px.line(df_nasa, x='Ngày', y='ET0 (mm/ngày)', title="Biến thiên ET0 (30 ngày qua)", markers=True)
                            st.plotly_chart(fig, use_container_width=True)
                            
                            avg_et0 = df_nasa["ET0 (mm/ngày)"].mean()
                            st.success(f"✅ ET0 Trung bình 30 ngày qua: **{avg_et0:.2f} mm/ngày**")
                        else:
                            st.warning("Không có dữ liệu hợp lệ từ NASA trong khoảng thời gian này.")
                            
                    except Exception as e:
                        st.error(f"Lỗi xử lý dữ liệu NASA: {e}")
                else:
                    st.error("Không thể tải dữ liệu từ NASA. Vui lòng thử lại sau.")


@st.cache_resource
def load_config():
    config_path = Path(".streamlit/appcfg.toml")
    if not config_path.exists():
        st.error(
            f"Cảnh báo: Không tìm thấy file cấu hình tại '{config_path}'. Sử dụng giá trị mặc định.")
        return {}
    try:
        return toml.load(config_path)
    except Exception as e:
        st.error(f"Lỗi khi đọc file cấu hình: {e}. Sử dụng giá trị mặc định.")
        return {}


config = load_config()
irrigation_cfg = config.get('irrigation', {})
caching_cfg = config.get('caching', {})

MOISTURE_MIN_THRESHOLD = irrigation_cfg.get('moisture_min_threshold', 25.0)
MOISTURE_MAX_THRESHOLD = irrigation_cfg.get('moisture_max_threshold', 55.0)
RAIN_THRESHOLD_MMH = irrigation_cfg.get('rain_threshold_mmh', 1.0)
TELEMETRY_HISTORY_TTL = caching_cfg.get('telemetry_history_ttl', 300)


@st.cache_data(ttl=TELEMETRY_HISTORY_TTL)
def get_field_telemetry_history(
        user_email: str,
        field_id: str) -> pd.DataFrame:
    hub_id = db.get(
        "iot_hubs", {
            "field_id": field_id, "user_email": user_email})
    if not hub_id:
        return pd.DataFrame()

    telemetry_data = db.get("telemetry", {"hub_id": hub_id[0].get('hub_id')})
    if not telemetry_data:
        return pd.DataFrame()

    records = []
    for entry in telemetry_data:
        timestamp = entry.get("timestamp")
        data = entry.get("data", {})

        nodes = data.get("soil_nodes", [])
        if nodes:
            values = [n['sensors']['soil_moisture'] for n in nodes if n.get(
                'sensors') and 'soil_moisture' in n['sensors']]
            if values:
                avg_moisture = sum(values) / len(values)
                records.append(
                    {"timestamp": timestamp, "Metric": "Độ ẩm đất (TB)", "Value": avg_moisture})

        atm_node = data.get("atmospheric_node", {})
        if atm_node.get(
                'sensors') and 'air_temperature' in atm_node['sensors']:
            records.append({"timestamp": timestamp,
                            "Metric": "Nhiệt độ không khí",
                            "Value": atm_node['sensors']['air_temperature']})

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.sort_values(by="timestamp")


def render_schedule():
    st.title("📅 Tình trạng & Lập kế hoạch tưới tiêu")
    st.markdown("Quản lý lịch tưới và trạng thái tưới tiêu.")

    if not (hasattr(st, 'user') and st.user.email):
        st.error("Vui lòng đăng nhập để xem.")
        return

    user_fields = db.get("fields", {"user_email": st.user.email})

    if not user_fields:
        st.warning("Không tìm thấy vườn. Vui lòng thêm vườn trước.")
        return

    st.subheader("🚀 Tính toán tưới tiêu hàng ngày")
    st.markdown("Nhấn nút này vào đầu mỗi ngày để tính toán lượng nước tưới khuyến nghị cho tất cả các vườn dựa trên thông số cây trồng và diện tích.")
    if st.button(
        "Tính toán nhu cầu tưới hôm nay cho tất cả các vườn",
            type="primary"):
        with st.spinner("Đang tính toán..."):
            updated_count = 0
            for field in user_fields:
                try:
                    # --- Fetch Telemetry ---
                    telemetry = None
                    hubs = db.get("iot_hubs", {"field_id": field.get('id'), "user_email": st.user.email})
                    if hubs:
                        hub_id = hubs[0].get('hub_id')
                        telemetry_data = db.get("telemetry", {"hub_id": hub_id})
                        if telemetry_data:
                             # Get the latest one
                             telemetry = sorted(telemetry_data, key=lambda x: x.get('timestamp', ''), reverse=True)[0]
                    
                    water_needs = predict_water_needs(field, telemetry)

                    update_data = {
                        "base_today_water": water_needs,
                        "base_time_needed": round(
                            water_needs / 20,
                            1) if water_needs > 0 else 0.0,
                        "today_water": water_needs,
                        "time_needed": round(
                            water_needs / 20,
                            1) if water_needs > 0 else 0.0,
                        "progress": 0,
                        "status": "dehydrated" if water_needs > 0 else "hydrated"}
                    if db.update(
                        "fields", {
                            "id": field.get('id')}, update_data):
                        updated_count += 1
                except Exception as e:
                    logger.error(
                        f"Lỗi khi tính toán cho vườn {
                            field.get('id')}: {e}")

            st.success(
                f"✅ Hoàn tất! Đã tính toán và cập nhật {updated_count}/{len(user_fields)} vườn.")
            st.cache_data.clear()
            st.rerun()

    field_options = {
        f"{
            field.get(
                'name',
                'Không tên')} ({
            field.get(
                'crop',
                'Không xác định')})": field for field in user_fields}
    selected_field_name = st.selectbox(
        "Chọn Vườn để xem chi tiết", options=list(
            field_options.keys()))
    selected_field = field_options[selected_field_name]

    # --- Thêm block NASA AOI ---
    render_nasa_info(selected_field)
    # ---------------------------

    tab1, tab2, tab3 = st.tabs(
        ["📊 Trạng thái hiện tại", "📈 Dự báo 7 ngày", "⚙️ Cài đặt tưới"])

    with tab1:
        render_current_status(selected_field, user_fields)
    with tab2:
        render_forecast(selected_field)
    with tab3:
        render_schedule_settings(selected_field)


def render_current_status(field, all_fields):
    st.subheader(f"📊 Trạng thái hiện tại: {field.get('name')}")

    if st.button("🔄 Cập nhật từ cảm biến"):
        get_field_telemetry_history.clear()
        st.rerun()

    live_stats = get_latest_telemetry_stats(
        field.get('user_email'), field.get('id'))

    db_status = field.get('status', 'hydrated')
    db_today_water = field.get('today_water', 0)
    db_time_needed = field.get('time_needed', 0)
    db_progress = field.get('progress', 0)

    display_status = db_status
    display_water = db_today_water
    display_time = db_time_needed
    display_progress = db_progress

    status_colors = {
        'hydrated': '#28a745',
        'dehydrated': '#ffc107',
        'severely_dehydrated': '#dc3545'}

    if live_stats and live_stats.get("avg_moisture") is not None:
        avg_moisture = live_stats["avg_moisture"]
        rain_intensity = live_stats["rain_intensity"]

        base_water = field.get('base_today_water', db_today_water)
        base_time = field.get('base_time_needed', db_time_needed)

        if rain_intensity > RAIN_THRESHOLD_MMH:
            display_status = "hydrated"
            display_progress = 100
            display_water = 0
            display_time = 0
            st.info(
                f"💧 Cảm biến phát hiện mưa ({rain_intensity} mm/h). Tự động ngưng tưới.")

        elif avg_moisture < MOISTURE_MIN_THRESHOLD:
            display_status = "dehydrated"
            display_progress = 0
            display_water = base_water
            display_time = base_time
            st.warning(f"Cảm biến phát hiện độ ẩm thấp: {avg_moisture:.1f}%.")

        elif avg_moisture > MOISTURE_MAX_THRESHOLD:
            display_status = "hydrated"
            display_progress = 100
            display_water = 0
            display_time = 0

        else:
            display_status = "hydrated"
            display_progress = int(
                (avg_moisture / MOISTURE_MAX_THRESHOLD) * 100)
            display_progress = max(0, min(100, display_progress))

            remaining_factor = 1.0 - (display_progress / 100.0)
            display_water = round(base_water * remaining_factor, 1)
            display_time = round(base_time * remaining_factor, 1)

        try:
            ts = datetime.fromisoformat(
                live_stats['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
            st.caption(f"Trạng thái live tính toán từ cảm biến (lúc {ts})")
        except BaseException:
            st.caption(f"Trạng thái live tính toán từ cảm biến.")

    else:
        st.error(
            "Không tìm thấy dữ liệu cảm biến (Hub/Sensor offline?). Hiển thị dữ liệu đã lưu cuối cùng.")

    st.markdown(
        f"**Trạng thái tưới:** <span style='color:{
            status_colors.get(
                display_status,
                '#6c757d')}; font-weight:bold;'>{
            display_status.title().replace(
                '_',
                ' ')}</span>",
        unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Lượng nước cần hôm nay", f"{display_water} m³")
    with col2:
        st.metric("Thời gian cần", f"{display_time} giờ")
    with col3:
        st.metric("Tiến độ", f"{display_progress}%")

    st.progress(display_progress, text=f"Tiến độ tưới: {display_progress}%")

    st.subheader("📋 Chi tiết vườn")
    col_a, col_b = st.columns(2)
    with col_a:
        st.write(f"**Cây trồng:** {field.get('crop', 'N/A')}")
        st.write(f"**Giai đoạn:** {field.get('stage', 'N/A')}")
    with col_b:
        st.write(f"**Diện tích:** {field.get('area', 0):.2f} ha")
        days_to_harvest = calculate_days_to_harvest(field)
        st.write(f"**Ngày thu hoạch:** {days_to_harvest} ngày" if days_to_harvest is not None else "N/A")

    st.subheader("📈 Tổng quan Nhu cầu tưới (Tất cả các vườn)")

    if all_fields:
        water_data = [
            {
                "Vườn": f.get(
                    'name',
                    'N/A'),
                "Lượng nước (m³)": f.get(
                    'today_water',
                    0),
                "Thời gian (giờ)": f.get(
                    'time_needed',
                    0)} for f in all_fields]
        df_water = pd.DataFrame(water_data)

        if df_water["Lượng nước (m³)"].sum() > 0:
            fig = px.bar(
                df_water,
                x='Vườn',
                y='Lượng nước (m³)',
                title='Lượng nước cần tưới hôm nay (m³)',
                hover_data=['Thời gian (giờ)'],
                color='Lượng nước (m³)',
                labels={
                    'Vườn': 'Tên Vườn'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tất cả các vườn đều đã được tưới hôm nay.")


def render_forecast(field):
    st.subheader(f"📈 Dự báo nhu cầu nước cho: {field.get('name')}")

    telemetry_df = get_field_telemetry_history(
        st.user.email, field.get('id', ''))

    if telemetry_df.empty or len(telemetry_df) < 2:
        st.warning(
            "Không đủ dữ liệu lịch sử để tạo dự báo. Cần ít nhất 2 điểm dữ liệu.")
        return

    soil_df = telemetry_df[telemetry_df['Metric'] == 'Độ ẩm đất (TB)'].copy()
    if len(soil_df) < 2:
        st.warning("Không đủ dữ liệu 'Độ ẩm đất' để tạo dự báo.")
        return

    with st.spinner("Đang tạo mô hình dự báo..."):
        try:
            soil_df['timestamp'] = pd.to_datetime(soil_df['timestamp'])
            soil_df = soil_df.sort_values(by='timestamp')

            # Use data from the last 14 days for a more relevant trend
            last_timestamp = soil_df['timestamp'].max()
            fourteen_days_ago = last_timestamp - timedelta(days=14)
            model_df = soil_df[soil_df['timestamp'] >= fourteen_days_ago].copy()

            # Fallback to all data if recent data is insufficient
            if len(model_df) < 2:
                st.warning(
                    "Không có đủ dữ liệu trong 14 ngày qua. Sử dụng tất cả dữ liệu lịch sử để dự báo.")
                model_df = soil_df.copy()

            # Using .loc to avoid SettingWithCopyWarning
            model_df.loc[:, 'days'] = (
                model_df['timestamp'] -
                model_df['timestamp'].min()).dt.total_seconds() / (
                24 *
                3600)

            X_train = model_df[['days']]
            y_train = model_df['Value']

            model = LinearRegression()
            model.fit(X_train, y_train)

            # Predict for the next 7 days from the last data point
            days_since_start = (
                last_timestamp - model_df['timestamp'].min()).total_seconds() / (
                24 * 3600)
            future_day_numbers = np.arange(
                days_since_start + 1,
                days_since_start + 8).reshape(-1, 1)

            # Fix for sklearn warning: pass a DataFrame with feature names
            future_days_df = pd.DataFrame(
                future_day_numbers, columns=['days'])
            future_predictions = model.predict(future_days_df)
            
            # --- Add Randomness (Noise) ---
            # Add normally distributed noise to simulate weather/soil variations
            # Scale is 2.0% moisture
            noise = np.random.normal(0, 2.0, size=future_predictions.shape)
            future_predictions += noise

            base_water = field.get('base_today_water', 0)
            if base_water == 0:
                base_water = predict_water_needs(field, None)

            water_needs_forecast = []
            for moisture in future_predictions:
                if moisture >= MOISTURE_MAX_THRESHOLD:
                    needed = 0
                elif moisture <= MOISTURE_MIN_THRESHOLD:
                    needed = base_water
                else:
                    # Inverse linear interpolation
                    needed = base_water * (
                        1 - (moisture - MOISTURE_MIN_THRESHOLD) /
                        (MOISTURE_MAX_THRESHOLD - MOISTURE_MIN_THRESHOLD))
                
                # Add small random variation to water need as well (e.g. +/- 5%)
                if needed > 0:
                     needed *= np.random.uniform(0.95, 1.05)

                water_needs_forecast.append(max(0, needed))

            # Simpler and more robust way to calculate future dates
            future_dates = [
                last_timestamp +
                timedelta(
                    days=i) for i in range(
                    1,
                    8)]
            forecast_df = pd.DataFrame(
                {'Date': future_dates, 'Lượng nước dự báo (m³)': water_needs_forecast})

            # --- Improved UI ---
            st.success("✅ Tạo mô hình dự báo & mô phỏng ngẫu nhiên thành công!")
            
            c1, c2, c3 = st.columns(3)
            total_forecast = sum(water_needs_forecast)
            avg_forecast = total_forecast / 7
            max_forecast = max(water_needs_forecast)
            
            c1.metric("Tổng lượng nước 7 ngày", f"{total_forecast:.1f} m³")
            c2.metric("Trung bình/ngày", f"{avg_forecast:.1f} m³")
            c3.metric("Ngày cao điểm", f"{max_forecast:.1f} m³")

            fig = px.bar(
                forecast_df,
                x='Date',
                y='Lượng nước dự báo (m³)',
                title='Dự báo lượng nước cần tưới trong 7 ngày tới (Mô phỏng)',
                labels={
                    'Date': 'Ngày',
                    'Lượng nước dự báo (m³)': 'Lượng nước dự báo (m³)'})
            fig.update_traces(marker_color='#00CC96')
            fig.update_layout(bargap=0.2)
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("Xem chi tiết dự báo (Dữ liệu bảng)"):
                st.dataframe(forecast_df.style.format(
                    {"Date": "{:%Y-%m-%d}", "Lượng nước dự báo (m³)": "{:.2f}"}))

        except Exception as e:
            st.error(f"Lỗi khi tạo dự báo: {e}")
            logger.error(f"Lỗi dự báo cho vườn {field.get('id')}: {e}")


def render_schedule_settings(field):
    st.subheader("⚙️ Cài đặt Lịch trình & Tối ưu hóa")

    st.write("**Cài đặt vườn hiện tại:**")
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Loại cây trồng", field.get('crop', 'Không xác định'))
        st.metric(
            "Giai đoạn sinh trưởng",
            field.get(
                'stage',
                'Không xác định'))
        st.metric("Diện tích", f"{field.get('area', 0):.2f} ha")

    with col2:
        st.metric("Hệ số cây trồng", field.get('crop_coefficient', 1.0))
        st.metric("Hiệu quả tưới",
                  f"{field.get('irrigation_efficiency', 85)}%")
        st.metric("Trạng thái hiện tại", field.get('status', 'Không xác định'))

    st.subheader("🔧 Cài đặt tối ưu hóa")

    with st.form("optimization_settings"):
        col1, col2 = st.columns(2)

        with col1:
            target_efficiency = st.slider(
                "Hiệu quả tưới mục tiêu (%)", 70, 95, field.get(
                    'irrigation_efficiency', 85))
            water_saving_mode = st.checkbox(
                "Chế độ tiết kiệm nước", value=False)
            weather_adjustment = st.checkbox(
                "Tự động điều chỉnh theo thời tiết", value=True)

        with col2:
            irrigation_frequency = st.selectbox(
                "Tần suất tưới", [
                    "Hàng ngày", "2 ngày một lần", "3 ngày một lần", "Hàng tuần"])
            preferred_time = st.selectbox(
                "Thời gian tưới ưu tiên", [
                    "Sáng sớm (6-8 giờ)", "Buổi tối (18-20 giờ)", "Linh hoạt"])
            max_duration = st.number_input(
                "Thời gian tưới tối đa (giờ)", 1, 12, 4)

        if st.form_submit_button("💾 Lưu cài đặt", type="primary"):
            update_data = {
                'irrigation_efficiency': target_efficiency,
                'water_saving_mode': water_saving_mode,
                'weather_adjustment': weather_adjustment,
                'irrigation_frequency': irrigation_frequency,
                'preferred_time': preferred_time,
                'max_duration': max_duration
            }

            try:
                if db.update("fields", {"id": field.get('id')}, update_data):
                    st.success("✅ Đã lưu cài đặt!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Lỗi: Không thể lưu cài đặt.")
            except Exception as e:
                st.error(f"Lỗi khi lưu: {e}")

    st.subheader("📊 Lịch sử dữ liệu cảm biến (Biểu đồ)")

    telemetry_df = get_field_telemetry_history(
        st.user.email, field.get('id', ''))

    if not telemetry_df.empty:
        fig = px.line(
            telemetry_df,
            x='timestamp',
            y='Value',
            color='Metric',
            title=f"Lịch sử cảm biến cho {
                field.get('name')}",
            labels={
                'timestamp': 'Ngày',
                'Value': 'Giá trị cảm biến'})
        st.plotly_chart(fig, use_container_width=True)

        st.write("**Thống kê gần đây:**")
        col1, col2 = st.columns(2)
        with col1:
            soil_data = telemetry_df[telemetry_df['Metric']
                                     == 'Độ ẩm đất (TB)']['Value']
            st.metric("Độ ẩm đất trung bình",
                      f"{soil_data.mean():.1f}%" if not soil_data.empty else "N/A")
        with col2:
            temp_data = telemetry_df[telemetry_df['Metric']
                                     == 'Nhiệt độ không khí']['Value']
            st.metric(
                "Nhiệt độ không khí trung bình", f"{
                    temp_data.mean():.1f}°C" if not temp_data.empty else "N/A")
    else:
        st.info(
            f"Không tìm thấy dữ liệu telemetry cho vườn này. Đảm bảo một Hub được gán cho vườn '{
                field.get('name')}' và đang gửi dữ liệu.")
