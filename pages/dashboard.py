import streamlit as st
import folium
from streamlit_folium import folium_static
import pandas as pd
import altair as alt
from datetime import datetime
from utils import get_default_fields
from database import db


def render_dashboard():
    st.set_page_config(page_title="Farm Dashboard", page_icon="🌾", layout="wide")
    telemetry = st.session_state.get("telemetry") or {}
    history = st.session_state.get("history", [])
    alerts = st.session_state.get("alerts", [])
    # Lấy fields từ database hoặc default
    user_fields = db.get_user_fields(st.user.email) if hasattr(st, 'user') and st.user.is_logged_in else []
    fields = user_fields if user_fields else st.session_state.get("fields") or get_default_fields()

    atm = telemetry.get("data", {}).get("atmospheric_node", {}).get("sensors", {})
    soil_nodes = telemetry.get("data", {}).get("soil_nodes", [])

    def average_soil(entry):
        data = entry.get("data", {}) if isinstance(entry, dict) else {}
        nodes = data.get("soil_nodes", [])
        if not nodes:
            return None
        values = [node.get("sensors", {}).get("soil_moisture") for node in nodes if node.get("sensors", {}).get("soil_moisture") is not None]
        if not values:
            return None
        return sum(values) / len(values)

    def delta(current, previous):
        if current is None or previous is None:
            return None
        return current - previous

    soil_avg = average_soil(telemetry)
    previous_avg = average_soil(history[-2]) if len(history) > 1 else None
    soil_delta = delta(soil_avg, previous_avg)

    prev_atm = history[-2]["data"].get("atmospheric_node", {}).get("sensors", {}) if len(history) > 1 and history[-2].get("data") else {}

    cols = st.columns(4, border=True)
    with cols[0]:
        temp = atm.get("air_temperature")
        prev_temp = prev_atm.get("air_temperature")
        label = f"{temp:.1f}°C" if temp is not None else "N/A"
        delta_value = delta(temp, prev_temp)
        st.metric("🌤 Air Temperature", label, f"{delta_value:+.1f}°C" if delta_value is not None else None)
    with cols[1]:
        label = f"{soil_avg:.1f}%" if soil_avg is not None else "N/A"
        st.metric("💧 Soil Moisture", label, f"{soil_delta:+.1f}%" if soil_delta is not None else None)
    with cols[2]:
        rain = atm.get("rain_intensity")
        prev_rain = prev_atm.get("rain_intensity")
        label = f"{rain:.1f} mm/h" if rain is not None else "N/A"
        delta_value = delta(rain, prev_rain)
        st.metric("🌧 Rain Intensity", label, f"{delta_value:+.1f}" if delta_value is not None else None)
    with cols[3]:
        wind = atm.get("wind_speed")
        prev_wind = prev_atm.get("wind_speed")
        label = f"{wind:.1f} m/s" if wind is not None else "N/A"
        delta_value = delta(wind, prev_wind)
        st.metric("🌬 Wind Speed", label, f"{delta_value:+.1f}" if delta_value is not None else None)

    # ========== FARM SUMMARY ==========
    st.subheader("Farm Overview")

    col1, col2 = st.columns([1.2, 1], border=True)

    field_df = pd.DataFrame(fields)
    field_df["Area (acres)"] = field_df["area"]
    crop_summary = field_df.groupby("crop", dropna=False)["Area (acres)"].sum().reset_index().rename(columns={"crop": "Crop"}) if not field_df.empty else pd.DataFrame(columns=["Crop", "Area (acres)"])
    crop_summary["Percentage"] = (crop_summary["Area (acres)"] / crop_summary["Area (acres)"].sum() * 100).round(1) if not crop_summary.empty else []
    total_area = field_df["area"].sum() if not field_df.empty else 0

    with col1:
        chart = (
            alt.Chart(crop_summary)
            .mark_arc(outerRadius=120)
            .encode(
                theta=alt.Theta("Area (acres):Q", stack=True),
                color=alt.Color("Crop:N", legend=alt.Legend(title="Crop")),
                tooltip=["Crop:N", "Area (acres):Q", "Percentage:Q"]
            )
            .properties(
                title="Crop Layout Preview",
                width=400,
                height=400
            )
            .configure_title(
                fontSize=18,
                fontWeight='bold',
                anchor='middle'
            )
            .configure_legend(
                orient="bottom"
            )
        ) if not crop_summary.empty else None

        if chart:
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No crop data available")

    with col2:
        st.metric("🌱 Total Cultivated Area: ", f"{int(total_area):,} acres" if total_area else "N/A")

        st.markdown("### Crop Summary")
        if not crop_summary.empty:
            st.dataframe(
                crop_summary.style.format({
                    "Area (acres)": "{:,.2f}",
                    "Percentage": "{:.1f}%"
                }).hide(axis="index"),
                use_container_width=True,
            )
        else:
            st.caption("Add fields to view crop distribution")

    # ========== FARM MAP ==========
    
    st.subheader("🌾 Farm Map")

    col_map, col_details = st.columns([2, 1])

    with col_details:
        with st.container(border=True, height=650):
            st.markdown("### 📋 Farm Details")
            
            selected_farm = st.selectbox(
                "Select a farm:",
                [f.get("name", f"Field {f.get('id', '')}") for f in fields],
                key="farm_select",
                help="Chọn vườn để xem chi tiết và highlight trên bản đồ",
                index=0  # Default to first farm to avoid initial rerun if possible
            )
            # Lấy thông tin farm tương ứng
            farm_data = next((f for f in fields if f.get("name", f"Field {f.get('id', '')}") == selected_farm), None)
            if farm_data:
                # Sử dụng columns để layout metrics đẹp hơn
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("🌱 Field Name", farm_data.get("name", "Unknown"))
                    st.metric("📏 Area", farm_data.get("area_display", f"{farm_data.get('area', 0):.2f} acres"))
                    st.metric("⏳ Days to Harvest", f"{farm_data.get('days_to_harvest', 'N/A')} days")
                
                with col2:
                    st.metric("🟢 Status", farm_data.get("status_label", farm_data.get("status", "Unknown")).title())
                    st.metric("💧 Daily Water Usage", farm_data.get("water_usage", "N/A"))
                    if farm_data.get("live_moisture") is not None:
                        st.metric("📡 Soil Moisture", f"{farm_data['live_moisture']}%")
                    if farm_data.get("soil_temperature") is not None:
                        st.metric("🔥 Soil Temp", f"{farm_data['soil_temperature']}°C")
                    
                # Thêm progress bar giả định cho harvest (ví dụ: giả sử total 90 days)
                progress_value = max(0, min(1, (90 - farm_data.get('days_to_harvest', 90)) / 90))
                st.progress(progress_value, text=f"Harvest Progress: {int(100 * progress_value)}%")
                
                # Thêm info box cho tips
                with st.expander("💡 Quick Tips", expanded=False):
                    st.info("AI treatment suggestions coming soon. Monitor telemetry for actionable insights today.")

    with col_map:
        with st.container(border=True, height=650):
            if fields:
                # Lấy farm được chọn từ session_state (now set before map)
                selected_farm_name = st.session_state.get("farm_select", fields[0].get("name", f"Field {fields[0].get('id', '')}"))
                
                # Xác định center dựa trên farm được chọn
                selected_farm_data = next((f for f in fields if f.get("name", f"Field {f.get('id', '')}") == selected_farm_name), fields[0])
                center_lat, center_lon = selected_farm_data.get("center", [20.455, 106.3375])

                m = folium.Map(location=[center_lat, center_lon], zoom_start=15, tiles='OpenStreetMap')

                # Vẽ từng farm dưới dạng polygon với highlight cho farm được chọn
                for field in fields:
                    if "polygon" in field:
                        # Highlight nếu là farm được chọn
                        if field.get("name", f"Field {field.get('id', '')}") == selected_farm_name:
                            color = "#ff0000"
                            fill_color = "#ff0000"
                            weight = 4
                            fill_opacity = 0.6
                        else:
                            color = "#3388ff"
                            fill_color = "#3388ff"
                            weight = 3
                            fill_opacity = 0.4
                        
                        popup_content = "<br>".join(filter(None, [
                            f"<b>{field.get('name', 'Field')}</b>",
                            f"Area: {field.get('area_display', f'{field.get('area', 0):.2f} acres')}" if field.get("area") is not None else None,
                            f"Days to Harvest: {field.get('days_to_harvest', 'N/A')} days",
                            f"Status: {field.get('status_label', field.get('status', 'N/A'))}",
                            f"Water Usage: {field.get('water_usage', 'N/A')}",
                            f"Soil Moisture: {field.get('live_moisture', 'N/A')}%" if field.get("live_moisture") is not None else None,
                        ]))
                        poly = folium.Polygon(
                            locations=field["polygon"],
                            color=color,
                            fill=True,
                            fill_color=fill_color,
                            fill_opacity=fill_opacity,
                            weight=weight,
                            popup=folium.Popup(popup_content, max_width=300)
                        )
                        poly.add_to(m)

                        # Marker ở giữa polygon để chọn nhanh, với icon khác cho selected
                        if "center" in field:
                            if field.get("name", f"Field {field.get('id', '')}") == selected_farm_name:
                                icon_color = "red"
                            else:
                                icon_color = "green"
                                
                            folium.Marker(
                                location=field["center"],
                                popup=folium.Popup(f"{field.get('name', 'Field')}", max_width=200),
                                tooltip=f"Click for {field.get('name', 'Field')}",
                                icon=folium.Icon(color=icon_color, icon="leaf", prefix="fa")
                            ).add_to(m)

                # Zoom to selected farm nếu có
                if selected_farm_data and "polygon" in selected_farm_data:
                    bounds = [[p[0], p[1]] for p in selected_farm_data["polygon"]]
                    m.fit_bounds(bounds, padding=0.1)

                folium_static(m, width="100%", height=650)
            else:
                st.info("⚠️ No farm location data found in session_state.")

    st.subheader("📈 Environmental Trends")
    history_records = []
    for entry in history:
        timestamp = entry.get("timestamp")
        for node in entry.get("data", {}).get("soil_nodes", []):
            sensors = node.get("sensors", {})
            if sensors.get("soil_moisture") is not None:
                history_records.append(
                    {
                        "timestamp": timestamp,
                        "node_id": node.get("node_id"),
                        "soil_moisture": sensors.get("soil_moisture"),
                    }
                )
    if history_records:
        history_df = pd.DataFrame(history_records)
        history_df["timestamp"] = pd.to_datetime(history_df["timestamp"])
        line_chart = (
            alt.Chart(history_df)
            .mark_line(point=True)
            .encode(
                x="timestamp:T",
                y=alt.Y("soil_moisture:Q", title="Soil Moisture (%)"),
                color="node_id:N",
                tooltip=["timestamp:T", "node_id:N", "soil_moisture:Q"],
            )
            .properties(height=350)
        )
        st.altair_chart(line_chart, use_container_width=True)
    else:
        st.caption("No telemetry history available yet")

    st.subheader("🚨 Active Alerts")
    if alerts:
        alerts_df = pd.DataFrame(alerts)
        st.dataframe(
            alerts_df.sort_values("created_at", ascending=False),
            use_container_width=True,
        )
    else:
        st.caption("No alerts triggered")

    st.subheader("🤖 AI Insights")
    st.info("Gemini and YOLO driven insights will appear here once integrated. Upload processing and conversational guidance are coming soon.")
                        
#render_dashboard()