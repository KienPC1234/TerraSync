import streamlit as st
import folium
from streamlit_folium import folium_static
import pandas as pd
import altair as alt
import logging
from database import db
from utils import check_warnings, calculate_days_to_harvest

logger = logging.getLogger(__name__)


@st.cache_data(ttl=60)
def load_dashboard_data(user_email: str):
    """
    Tải tất cả dữ liệu cần thiết cho dashboard từ DB và lọc theo user_email.
    """
    try:
        user_hubs = db.get("iot_hubs", {"user_email": user_email})
        user_hub_ids = [h['hub_id'] for h in user_hubs]
        user_fields = db.get("fields", {"user_email": user_email})
        all_telemetry = db.get("telemetry")
        all_alerts = db.get("alerts")

        user_history = sorted(
            [t for t in all_telemetry if t.get('hub_id') in user_hub_ids],
            key=lambda x: x.get('timestamp', '1970-01-01T00:00:00+00:00')
        )

        user_alerts = [a for a in all_alerts if a.get(
            'hub_id') in user_hub_ids]
        latest_telemetry = user_history[-1] if user_history else {}

        return latest_telemetry, user_history, user_alerts, user_fields
    except Exception as e:
        logger.error(f"Lỗi khi tải dữ liệu dashboard: {e}")
        return {}, [], [], []


def average_soil(entry):
    data = entry.get("data", {}) if isinstance(entry, dict) else {}
    nodes = data.get("soil_nodes", [])
    if not nodes:
        return None
    values = [
        node.get(
            "sensors",
            {}).get("soil_moisture") for node in nodes if node.get(
            "sensors",
            {}).get("soil_moisture") is not None]
    if not values:
        return None
    return sum(values) / len(values)


def delta(current, previous):
    if current is None or previous is None:
        return None
    return current - previous


def render_dashboard():
    if not (hasattr(st, 'user') and st.user.email):
        st.warning("⚠️ Vui lòng đăng nhập để xem Dashboard.")
        return

    telemetry, history, alerts, fields = load_dashboard_data(st.user.email)

    if not fields and not history:
        st.info(
            "👋 Chào mừng bạn! Hãy thêm Vườn (Field) và Hub IoT để bắt đầu.")
        return

    atm = telemetry.get(
        "data",
        {}).get(
        "atmospheric_node",
        {}).get(
            "sensors",
        {})
    soil_avg = average_soil(telemetry)
    previous_avg = average_soil(history[-2]) if len(history) > 1 else None
    soil_delta = delta(soil_avg, previous_avg)

    prev_atm = {}
    if len(history) > 1 and history[-2].get("data"):
        prev_atm = history[-2]["data"].get("atmospheric_node",
                                           {}).get("sensors", {})

    cols = st.columns(4, border=True)
    with cols[0]:
        temp = atm.get("air_temperature")
        prev_temp = prev_atm.get("air_temperature")
        label = f"{temp:.1f}°C" if temp is not None else "N/A"
        delta_value = delta(temp, prev_temp)
        st.metric(
            "🌤 Nhiệt độ không khí",
            label,
            f"{delta_value:+.1f}°C" if delta_value is not None else None)
    with cols[1]:
        label = f"{soil_avg:.1f}%" if soil_avg is not None else "N/A"
        st.metric("💧 Độ ẩm đất", label,
                  f"{soil_delta:+.1f}%" if soil_delta is not None else None)
    with cols[2]:
        rain = atm.get("rain_intensity")
        prev_rain = prev_atm.get("rain_intensity")
        label = f"{rain:.1f} mm/h" if rain is not None else "N/A"
        delta_value = delta(rain, prev_rain)
        st.metric(
            "🌧 Lượng mưa",
            label,
            f"{delta_value:+.1f}" if delta_value is not None else None)
    with cols[3]:
        wind = atm.get("wind_speed")
        prev_wind = prev_atm.get("wind_speed")
        label = f"{wind:.1f} m/s" if wind is not None else "N/A"
        delta_value = delta(wind, prev_wind)
        st.metric(
            "🌬 Tốc độ gió",
            label,
            f"{delta_value:+.1f}" if delta_value is not None else None)

    st.subheader("Tổng quan trang trại")
    col1, col2 = st.columns([1.2, 1], border=True)

    if fields:
        field_df = pd.DataFrame(fields)
        field_df["Area (ha)"] = field_df["area"]
        crop_summary = field_df.groupby(
            "crop", dropna=False)["Area (ha)"].sum().reset_index().rename(
            columns={
                "crop": "Loại cây trồng"})
        crop_summary["Percentage"] = (
            crop_summary["Area (ha)"] /
            crop_summary["Area (ha)"].sum() *
            100).round(1)
        total_area = field_df["area"].sum()
    else:
        field_df = pd.DataFrame(columns=["crop", "area"])
        crop_summary = pd.DataFrame(columns=["Loại cây trồng", "Area (ha)"])
        total_area = 0

    with col1:
        if not crop_summary.empty:
            chart = (
                alt.Chart(crop_summary).mark_arc(
                    outerRadius=120).encode(
                    theta=alt.Theta(
                        "Area (ha):Q",
                        stack=True),
                    color=alt.Color(
                        "Loại cây trồng:N",
                        legend=alt.Legend(
                            title="Loại cây trồng")),
                    tooltip=[
                        "Loại cây trồng:N",
                        "Area (ha):Q",
                        "Percentage:Q"]).properties(
                    title="Phân bổ cây trồng",
                    width=400,
                    height=400))
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("Thêm vườn để xem phân bổ cây trồng.")

    with col2:
        st.metric("🌱 Tổng diện tích canh tác: ",
                  f"{total_area:,.2f} ha" if total_area else "N/A")
        st.markdown("### Thống kê cây trồng")
        if not crop_summary.empty:
            st.dataframe(
                crop_summary.style.format(
                    {
                        "Area (ha)": "{:,.2f}",
                        "Percentage": "{:.1f}%"}).hide(
                    axis="index"),
                use_container_width=True,
            )
        else:
            st.caption("Không có dữ liệu vườn.")

    st.subheader("Bản đồ trang trại")
    col_map, col_details = st.columns([2, 1])

    with col_details:
        with st.container(border=True, height=650):
            st.markdown("### Chi tiết trang trại")

            if fields:
                mappable_fields = [f for f in fields if f.get('polygon')]
                selected_farm = st.selectbox(
                    "Chọn một trang trại:",
                    [f.get("name", f"Vườn {f.get('id', '')[:8]}")
                     for f in mappable_fields],
                    key="farm_select",
                    help="Chọn vườn để xem chi tiết và đánh dấu trên bản đồ",
                )

                farm_data = next(
                    (f for f in mappable_fields if f.get(
                        "name",
                        f"Vườn {f.get('id', '')[:8]}") == selected_farm),
                    None)

                if farm_data:
                    days_to_harvest = calculate_days_to_harvest(farm_data)
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(
                            "🌱 Tên vườn", farm_data.get(
                                "name", "Không rõ"))
                        st.metric(
                            "📏 Diện tích",
                            f"{farm_data.get('area', 0):.2f} ha")
                        st.metric(
                            "⏳ Ngày thu hoạch",
                            f"{days_to_harvest} ngày" if days_to_harvest is not None else "N/A")

                    with col2:
                        st.metric(
                            "🟢 Trạng thái",
                            farm_data.get("status", "Không rõ").title())
                        st.metric(
                            "💧 Nước tưới hàng ngày",
                            f"{farm_data.get('today_water', 'N/A')} m³")
                        st.metric(
                            "🌿 Loại cây trồng", farm_data.get("crop", "N/A"))

                    watering_progress = farm_data.get('progress', 0)
                    st.progress(
                        watering_progress / 100,
                        text=f"Tiến độ tưới: {watering_progress}%")

                    node_id = farm_data.get("node_id")
                    if node_id and telemetry:
                        node_data = next(
                            (n for n in telemetry.get(
                                "data",
                                {}).get(
                                "soil_nodes",
                                []) if n.get("node_id") == node_id),
                            None)
                        if node_data:
                            st.markdown("---")
                            st.markdown("#### Dữ liệu cảm biến trực tiếp")
                            sensors = node_data.get("sensors", {})
                            st.metric(
                                "🌡️ Nhiệt độ đất",
                                f"{sensors.get('soil_temperature'):.1f}°C"
                                if sensors.get('soil_temperature')
                                is not None else "N/A")
                            st.metric(
                                "💧 Độ ẩm đất",
                                f"{sensors.get('soil_moisture'):.1f}%"
                                if sensors.get('soil_moisture')
                                is not None else "N/A")

                    warnings = check_warnings(farm_data, telemetry)
                    if warnings:
                        st.markdown("---")
                        st.markdown("#### Cảnh báo")
                        for warning in warnings:
                            st.warning(warning)
            else:
                st.info("Không có vườn nào để hiển thị chi tiết.")

    with col_map:
        with st.container(border=True, height=650):
            if farm_data and farm_data.get("center"):
                center_lat, center_lon = farm_data.get(
                    "center", [20.455, 106.3375])
            elif fields and fields[0].get("center"):
                center_lat, center_lon = fields[0].get(
                    "center", [20.455, 106.3375])
            else:
                center_lat, center_lon = 20.455, 106.3375

            m = folium.Map(
                location=[
                    center_lat,
                    center_lon],
                zoom_start=15,
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attr='Esri')

            for field in fields:
                if "polygon" in field and field.get('polygon'):
                    is_selected = (
                        farm_data and field.get('id') == farm_data.get('id'))
                    color = "#ff0000" if is_selected else "#3388ff"
                    weight = 4 if is_selected else 3
                    fill_opacity = 0.6 if is_selected else 0.4

                    popup_content = f"""
                    <b>{field.get('name', 'Vườn')}</b><br>
                    Loại cây: {field.get('crop', 'N/A')}<br>
                    Diện tích: {field.get('area', 0):.2f} ha<br>
                    Trạng thái: {field.get('status', 'N/A')}
                    """

                    try:
                        folium.Polygon(
                            locations=field["polygon"],
                            color=color,
                            fill=True,
                            fill_color=color,
                            fill_opacity=fill_opacity,
                            weight=weight,
                            popup=folium.Popup(popup_content, max_width=300)
                        ).add_to(m)
                    except Exception as map_e:
                        logger.warning(
                            f"Không thể vẽ polygon cho field "
                            f"{field.get('id')}: {map_e}")

                    if "center" in field:
                        folium.Marker(
                            location=field["center"],
                            popup=folium.Popup(
                                f"{field.get('name', 'Vườn')}", max_width=200),
                            tooltip=f"Nhấn để xem {field.get('name', 'Vườn')}",
                            icon=folium.Icon(
                                color="red" if is_selected else "green",
                                icon="leaf",
                                prefix="fa")
                        ).add_to(m)

            if farm_data and farm_data.get("polygon"):
                try:
                    bounds = [[p[0], p[1]] for p in farm_data["polygon"]]
                    m.fit_bounds(bounds, padding=(0.001, 0.001))
                except Exception:
                    pass

            folium_static(m, width="100%", height=630)

    with st.container(border=True):
        st.subheader("📈 Xu hướng môi trường")
        history_records = []

        for entry in history:
            timestamp = entry.get("timestamp")
            if entry.get(
                "data",
                {}).get(
                "atmospheric_node",
                {}).get(
                "sensors",
                    {}):
                atm_sensors = entry["data"]["atmospheric_node"]["sensors"]
                history_records.append({"timestamp": timestamp,
                                        "Sensor": "Nhiệt độ không khí",
                                        "Value": atm_sensors.get("air_temperature")})
                history_records.append({"timestamp": timestamp,
                                        "Sensor": "Độ ẩm không khí",
                                        "Value": atm_sensors.get("air_humidity")})

            avg_moisture = average_soil(entry)
            if avg_moisture is not None:
                history_records.append(
                    {"timestamp": timestamp,
                     "Sensor": "Độ ẩm đất (TB)",
                     "Value": avg_moisture})

        if history_records:
            history_df = pd.DataFrame(history_records).dropna()
            history_df["timestamp"] = pd.to_datetime(history_df["timestamp"])

            line_chart = (
                alt.Chart(history_df)
                .mark_line(point=True)
                .encode(
                    x="timestamp:T",
                    y=alt.Y("Value:Q"),
                    color="Sensor:N",
                    tooltip=["timestamp:T", "Sensor:N", "Value:Q"],
                )
                .properties(height=350)
                .interactive()
            )
            st.altair_chart(line_chart, use_container_width=True)
        else:
            st.caption("Không có lịch sử telemetry để vẽ biểu đồ.")

    with st.container(border=True):
        st.subheader("🚨 Cảnh báo đang hoạt động")
        if alerts:
            alerts_df = pd.DataFrame(alerts)
            st.dataframe(
                alerts_df.sort_values(
                    "created_at",
                    ascending=False),
                use_container_width=True,
                column_config={
                    "created_at": st.column_config.DatetimeColumn(
                        "Thời gian",
                        format="YYYY-MM-DD HH:mm"),
                    "level": "Mức độ",
                    "message": "Thông điệp",
                    "hub_id": "Hub",
                    "node_id": "Node",
                })
        else:
            st.success(
                "🎉 Không có cảnh báo nào. Hệ thống hoạt động bình thường!")
