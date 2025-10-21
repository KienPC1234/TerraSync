import streamlit as st
import folium
from streamlit_folium import folium_static
import pandas as pd
import altair as alt
from datetime import datetime


def render_dashboard():
    st.set_page_config(page_title="Farm Dashboard", page_icon="🌾", layout="wide")
    # ========== WEATHER / ENVIRONMENT METRICS ==========
    cols = st.columns(4, border=True)
    with cols[0]:
        st.metric("🌤 Temperature", "21°C", "Partly Cloudy")
    with cols[1]:
        st.metric("💧 Soil Moisture", "72%", "High")
    with cols[2]:
        st.metric("🌧 Precipitation", "-2mm", "Low")
    with cols[3]: 
        st.metric("🌬 Wind Speed", "10 km/h", "Windy")

    # ========== FARM SUMMARY ==========
    st.subheader("Farm Overview")

    col1, col2 = st.columns([1.2, 1], border=True)

    with col1:
        # Data
        crops = {
            "Wheat": 1395.93,
            "Barley": 1125.75,
            "Corn": 720.48,
            "Blueberry": 675.45,
            "Avocado": 585.39
        }

        # Convert to DataFrame
        df = pd.DataFrame({
            "Crop": list(crops.keys()),
            "Area (acres)": list(crops.values())
        })

        # Tính tổng và phần trăm
        total_area = df["Area (acres)"].sum()
        df["Percentage"] = (df["Area (acres)"] / total_area * 100).round(1)

        # Altair pie chart
        chart = (
            alt.Chart(df)
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
        )

        st.altair_chart(chart, use_container_width=True)

    with col2:
        st.metric("🌱 Total Cultivated Area: ", f"{int(total_area):,} acres")

        st.markdown("### Crop Summary")
        # Hiển thị bảng dữ liệu
        st.dataframe(
            df.style.format({
                "Area (acres)": "{:,.2f}",
                "Percentage": "{:.1f}%"
            }).hide(axis="index"),
            use_container_width=True,
        )

    # ========== FARM MAP ==========
    
    if not hasattr(st.session_state, 'fields'):
        st.session_state.fields = [
            {
                "name": "Blueberry Farm",
                "area": "675.45 acres",
                "days_to_harvest": 48,
                "status": "Hydrated",
                "water_usage": "180 gallons/day",
                "polygon": [
                    [20.453, 106.335],
                    [20.457, 106.335],
                    [20.457, 106.340],
                    [20.453, 106.340]
                ],
                "center": [20.455, 106.3375]
            },
            {
                "name": "Strawberry Farm",
                "area": "512.30 acres",
                "days_to_harvest": 32,
                "status": "Moderate",
                "water_usage": "150 gallons/day",
                "polygon": [
                    [20.460, 106.345],
                    [20.464, 106.345],
                    [20.464, 106.350],
                    [20.460, 106.350]
                ],
                "center": [20.462, 106.3475]
            }
        ]
    
    st.subheader("🌾 Farm Map")

    col_map, col_details = st.columns([2, 1])

    with col_details:
        with st.container(border=True, height=650):
            st.markdown("### 📋 Farm Details")
            
            selected_farm = st.selectbox(
                "Select a farm:",
                [f["name"] for f in st.session_state.fields],
                key="farm_select",
                help="Chọn vườn để xem chi tiết và highlight trên bản đồ",
                index=0  # Default to first farm to avoid initial rerun if possible
            )
            # Lấy thông tin farm tương ứng
            farm_data = next((f for f in st.session_state.fields if f["name"] == selected_farm), None)
            if farm_data:
                # Sử dụng columns để layout metrics đẹp hơn
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("🌱 Field Name", farm_data["name"])
                    st.metric("📏 Area", farm_data["area"])
                    st.metric("⏳ Days to Harvest", f"{farm_data['days_to_harvest']} days")
                
                with col2:
                    st.metric("🟢 Status", farm_data.get("status", "Unknown"))
                    st.metric("💧 Daily Water Usage", farm_data.get("water_usage", "N/A"))
                    
                # Thêm progress bar giả định cho harvest (ví dụ: giả sử total 90 days)
                progress_value = max(0, min(1, (90 - farm_data['days_to_harvest']) / 90))
                st.progress(progress_value, text=f"Harvest Progress: {int(100 * progress_value)}%")
                
                # Thêm info box cho tips
                with st.expander("💡 Quick Tips", expanded=False):
                    st.info(f"Monitor {farm_data['status'].lower()} levels closely for optimal yield in {farm_data['name']}.")

    with col_map:
        with st.container(border=True, height=650):
            if st.session_state.get("fields"):
                # Lấy farm được chọn từ session_state (now set before map)
                selected_farm_name = st.session_state.get("farm_select", st.session_state.fields[0]["name"])
                
                # Xác định center dựa trên farm được chọn
                selected_farm_data = next((f for f in st.session_state.fields if f["name"] == selected_farm_name), st.session_state.fields[0])
                center_lat, center_lon = selected_farm_data["center"]

                m = folium.Map(location=[center_lat, center_lon], zoom_start=15, tiles='OpenStreetMap')

                # Vẽ từng farm dưới dạng polygon với highlight cho farm được chọn
                for field in st.session_state.fields:
                    if "polygon" in field:
                        # Highlight nếu là farm được chọn
                        if field["name"] == selected_farm_name:
                            color = "#ff0000"
                            fill_color = "#ff0000"
                            weight = 4
                            fill_opacity = 0.6
                        else:
                            color = "#3388ff"
                            fill_color = "#3388ff"
                            weight = 3
                            fill_opacity = 0.4
                        
                        poly = folium.Polygon(
                            locations=field["polygon"],
                            color=color,
                            fill=True,
                            fill_color=fill_color,
                            fill_opacity=fill_opacity,
                            weight=weight,
                            popup=folium.Popup(
                                f"<b>{field['name']}</b><br>Area: {field['area']}<br>Days to Harvest: {field['days_to_harvest']} days<br>Status: {field.get('status', 'N/A')}<br>Water Usage: {field.get('water_usage', 'N/A')}",
                                max_width=300
                            )
                        )
                        poly.add_to(m)

                        # Marker ở giữa polygon để chọn nhanh, với icon khác cho selected
                        if "center" in field:
                            if field["name"] == selected_farm_name:
                                icon_color = "red"
                            else:
                                icon_color = "green"
                                
                            folium.Marker(
                                location=field["center"],
                                popup=folium.Popup(f"{field['name']}", max_width=200),
                                tooltip=f"Click for {field['name']}",
                                icon=folium.Icon(color=icon_color, icon="leaf", prefix="fa")
                            ).add_to(m)

                # Zoom to selected farm nếu có
                if selected_farm_data and "polygon" in selected_farm_data:
                    bounds = [[p[0], p[1]] for p in selected_farm_data["polygon"]]
                    m.fit_bounds(bounds, padding=0.1)

                folium_static(m, width="100%", height=650)
            else:
                st.info("⚠️ No farm location data found in session_state.")
                        
#render_dashboard()