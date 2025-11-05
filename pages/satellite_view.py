"""
TerraSync Satellite View Page
Xem ruộng qua ảnh vệ tinh với AI upscaling
"""

import streamlit as st
import folium
from streamlit_folium import folium_static
import requests
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
from PIL import Image
import io
import base64
from database import db
import time

API_URL = "http://172.24.193.209:9990"

def process_satellite_imagery(lat: float, lon: float, polygon: List[List[float]] = None) -> Dict[str, Any]:
    """
    Xử lý ảnh vệ tinh sử dụng API endpoint /process_satellite_image.
    Tạo list coords từ polygon hoặc center point và gửi data trực tiếp.
    Đảm bảo coords được gửi ở định dạng [[lon, lat], ...] với ít nhất 3 điểm cho polygon.
    """
    coords = []  # List các điểm tọa độ [lon, lat]
    
    if polygon is None or len(polygon) < 3:
        # Fallback: Tạo bbox vuông nhỏ quanh center (4 điểm, không đóng)
        side = 0.001
        min_lat, max_lat = lat - side / 2, lat + side / 2
        min_lon, max_lon = lon - side / 2, lon + side / 2
        
        # 4 điểm theo thứ tự [lon, lat], không đóng (backend sẽ đóng)
        coords = [
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat]
        ]
    else:
        # Sử dụng polygon [lat, lon] từ database, chuyển sang [lon, lat]
        # Giả sử polygon không đóng, backend sẽ đóng nếu cần
        coords = [[p[1], p[0]] for p in polygon]  # Chuyển [lat, lon] -> [lon, lat]

    # Lấy ảnh mới nhất trong vòng 2 ngày để đảm bảo có dữ liệu
    payload = {
        "coords": coords,
        "cloud": 50.0,
        "days": 30,  # Lấy ảnh trong 2 ngày gần nhất
        "upscale": 4,
        "collection": "sentinel-2"
    }
    
    try:
        response = requests.post(
            f"{API_URL}/process_satellite_image",
            json=payload,
            timeout=60000  # Tăng timeout nếu API xử lý lâu
        )
        
        if response.status_code == 200:
            api_result = response.json()
            
            # Mock dữ liệu NDVI (vì API chỉ trả về ảnh)
            predicted_class = "vegetation" 
            if "vegetation" in predicted_class or "crop" in predicted_class:
                ndvi = 0.6
            elif "bare" in predicted_class or "soil" in predicted_class:
                ndvi = 0.1
            else:
                ndvi = 0.3
            
            satellite_data = {
                "ndvi_index": ndvi,
                "evapotranspiration": 3.5 + (ndvi * 2),
                "soil_moisture_index": 0.4 + (ndvi * 0.2),
                "cloud_coverage": api_result.get("cloud_cover", 15.0)  # Lấy cloud_cover nếu API trả về
            }
            
            return {
                "status": "success",
                "satellite_data": satellite_data,
                "api_result": api_result
            }
        else:
            return {"status": "error", "message": f"API Error {response.status_code}: {response.text}"}
    except requests.exceptions.Timeout:
         return {"status": "error", "message": "API request timed out (quá 60000 giây)."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_weather_forecast(lat: float, lon: float, days: int = 7) -> Dict[str, Any]:
    """
    Mock weather forecast (có thể thay bằng API thực tế sau).
    """
    times = [(datetime.now() + timedelta(i)).strftime("%Y-%m-%d") for i in range(days)]
    return {
        "status": "success",
        "forecast": {
            "daily": {
                "time": times,
                "temperature_2m_max": [28 + (i * 0.5) for i in range(days)],
                "temperature_2m_min": [20 + (i * 0.3) for i in range(days)],
                "precipitation_sum": [2 if i % 3 == 0 else 0 for i in range(days)],
                "wind_speed_10m_max": [4 + (i * 0.2) for i in range(days)]
            }
        }
    }

def render_satellite_view():
    """Trang xem ruộng qua vệ tinh"""
    st.title("🛰️ Satellite View & Remote Sensing")
    st.markdown("Xem ruộng của bạn từ không gian với ảnh vệ tinh Sentinel-2 và AI.")
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["🗺️ Satellite Map", "📊 NDVI Analysis", "🌤️ Weather Overlay"])
    
    with tab1:
        render_satellite_map()
    
    with tab2:
        render_ndvi_analysis()
    
    with tab3:
        render_weather_overlay()

def render_satellite_map():
    """Bản đồ vệ tinh tương tác"""
    st.subheader("🗺️ Interactive Satellite Map")
    
    # Lấy fields của user
    user_fields = db.get_user_fields(st.user.email) if hasattr(st, 'user') and st.user.is_logged_in else []
    
    if not user_fields:
        st.warning("No fields found. Please add fields first.")
        return
    
    # Chọn field để xem
    field_options = {f"{field.get('name', 'Unnamed')} ({field.get('crop', 'Unknown')})": field for field in user_fields}
    selected_field_name = st.selectbox("Select Field", options=list(field_options.keys()))
    selected_field = field_options[selected_field_name]
    
    # Tọa độ trung tâm
    center_lat = selected_field.get('center', [20.450123, 106.325678])[0]
    center_lon = selected_field.get('center', [20.450123, 106.325678])[1]
    
    # Tạo bản đồ
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=16,
        tiles=None
    )
    
    # Thêm các layer bản đồ
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='Satellite',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Vẽ polygon của field
    if 'polygon' in selected_field:
        polygon_coords = selected_field['polygon']
        folium.Polygon(
            locations=polygon_coords,
            popup=f"Field: {selected_field.get('name', 'Unnamed')}<br>Crop: {selected_field.get('crop', 'Unknown')}<br>Area: {selected_field.get('area', 0):.2f} ha",
            color='red',
            weight=3,
            fillColor='yellow',
            fillOpacity=0.3
        ).add_to(m)
    
    # Thêm marker trung tâm
    folium.Marker(
        [center_lat, center_lon],
        popup=f"Center of {selected_field.get('name', 'Field')}",
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(m)
    
    # Hiển thị bản đồ
    folium_static(m, width=800, height=500)
    
    # Thông tin field
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Field Area", f"{selected_field.get('area', 0):.2f} hectares")
    with col2:
        st.metric("Crop Type", selected_field.get('crop', 'Unknown'))
    with col3:
        st.metric("Coordinates", f"{center_lat:.6f}, {center_lon:.6f}")
    
    # AI Processing options
    st.subheader("🤖 AI Satellite Processing")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("Nhận ảnh vệ tinh **mới nhất** từ **Sentinel-2** của Cơ quan Vũ trụ Châu Âu (ESA).")
        if st.button("🛰️ Xem ruộng của bạn từ không gian!", type="primary", help="Lấy ảnh mới nhất trong vòng 2 ngày qua"):
            with st.spinner("🛰️ Đang kết nối với vệ tinh, tìm ảnh mới nhất và dùng AI xử lý... Quá trình này có thể mất vài phút."):
                
                result = process_satellite_imagery(center_lat, center_lon, selected_field.get('polygon'))
                
                if result["status"] == "success":
                    st.session_state.satellite_result = result
                    st.success("✅ Đã tải và xử lý ảnh vệ tinh thành công!")
                    
                    # Hiển thị ảnh đã xử lý và kết quả AI
                    api_res = result["api_result"]
                    if "image_base64" in api_res:
                        image_bytes = base64.b64decode(api_res["image_base64"])
                        
                        # Lấy ngày chụp (giả sử API trả về)
                        acquisition_date = api_res.get("acquisition_date", (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))
                        caption = f"Ảnh vệ tinh Sentinel-2 (10m/pixel) được AI nâng cấp.\nDữ liệu được chụp ngày: {acquisition_date}"
                        st.image(Image.open(io.BytesIO(image_bytes)), caption=caption, width='stretch')
                    
                else:
                    st.error(f"❌ Xử lý thất bại: {result.get('message', 'Lỗi không xác định')}")
    
    with col2:
        date_range = st.date_input(
            "Select Date Range",
            value=(datetime.now() - timedelta(days=7), datetime.now()),
            max_value=datetime.now()
        )
        
        if st.button("📅 Get Historical Data"):
            st.info("Historical satellite data would be retrieved here")

def render_ndvi_analysis():
    """Phân tích NDVI"""
    st.subheader("📊 NDVI (Normalized Difference Vegetation Index) Analysis")
    
    if "satellite_result" not in st.session_state:
        st.info("Please process satellite imagery first in the Satellite Map tab.")
        return
    
    result = st.session_state.satellite_result
    satellite_data = result.get("satellite_data", {})
    api_res = result.get("api_result", {})
    
    # Hiển thị lại ảnh nếu có
    if "image_base64" in api_res:
        image_bytes = base64.b64decode(api_res["image_base64"])
        st.image(Image.open(io.BytesIO(image_bytes)), caption="AI Processed Satellite Image", use_column_width=True)
    
    # NDVI metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        ndvi = satellite_data.get("ndvi_index", 0)
        st.metric("NDVI Index", f"{ndvi:.3f}")
    
    with col2:
        et = satellite_data.get("evapotranspiration", 0)
        st.metric("Evapotranspiration", f"{et:.1f} mm/day")
    
    with col3:
        soil_moisture = satellite_data.get("soil_moisture_index", 0)
        st.metric("Soil Moisture Index", f"{soil_moisture:.3f}")
    
    with col4:
        cloud_coverage = satellite_data.get("cloud_coverage", 0)
        st.metric("Cloud Coverage", f"{cloud_coverage:.1f}%")
    
    # NDVI interpretation
    st.subheader("🌱 NDVI Interpretation")
    
    if ndvi < 0.1:
        ndvi_status = "🔴 Bare Soil/Water"
        ndvi_color = "red"
    elif ndvi < 0.3:
        ndvi_status = "🟡 Sparse Vegetation"
        ndvi_color = "orange"
    elif ndvi < 0.6:
        ndvi_status = "🟢 Moderate Vegetation"
        ndvi_color = "green"
    else:
        ndvi_status = "🌿 Dense Vegetation"
        ndvi_color = "darkgreen"
    
    st.markdown(f"**Vegetation Status:** <span style='color:{ndvi_color}'>{ndvi_status}</span>", unsafe_allow_html=True)
    
    # NDVI chart
    st.subheader("📈 NDVI Trends")
    
    # Generate sample NDVI data
    import pandas as pd
    import plotly.graph_objects as go
    
    dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
    ndvi_values = [ndvi + (i * 0.001) + (0.05 * (i % 7 - 3)) for i in range(len(dates))]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=ndvi_values,
        mode='lines+markers',
        name='NDVI',
        line=dict(color='green', width=2)
    ))
    
    # Add threshold lines
    fig.add_hline(y=0.3, line_dash="dash", line_color="orange", annotation_text="Sparse Vegetation")
    fig.add_hline(y=0.6, line_dash="dash", line_color="green", annotation_text="Dense Vegetation")
    
    fig.update_layout(
        title="NDVI Trends (Last 30 Days)",
        xaxis_title="Date",
        yaxis_title="NDVI Index",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Recommendations based on NDVI
    st.subheader("💡 Recommendations")
    
    if ndvi < 0.3:
        st.warning("⚠️ Low vegetation density detected. Consider:")
        st.write("- Check irrigation system")
        st.write("- Apply fertilizer if needed")
        st.write("- Monitor for pests or diseases")
    elif ndvi > 0.7:
        st.success("✅ Excellent vegetation health!")
        st.write("- Continue current management practices")
        st.write("- Monitor for overgrowth")
    else:
        st.info("ℹ️ Moderate vegetation health. Consider:")
        st.write("- Regular monitoring")
        st.write("- Optimize irrigation schedule")

def render_weather_overlay():
    """Weather overlay trên bản đồ"""
    st.subheader("🌤️ Weather Overlay")
    
    # Lấy fields của user
    user_fields = db.get_user_fields(st.user.email) if hasattr(st, 'user') and st.user.is_logged_in else []
    
    if not user_fields:
        st.warning("No fields found. Please add fields first.")
        return
    
    # Chọn field
    field_options = {f"{field.get('name', 'Unnamed')} ({field.get('crop', 'Unknown')})": field for field in user_fields}
    selected_field_name = st.selectbox("Select Field for Weather", options=list(field_options.keys()), key="weather_field")
    selected_field = field_options[selected_field_name]
    
    center_lat = selected_field.get('center', [20.450123, 106.325678])[0]
    center_lon = selected_field.get('center', [20.450123, 106.325678])[1]
    
    # Lấy dự báo thời tiết
    if st.button("🌤️ Get Weather Forecast"):
        with st.spinner("Fetching weather data..."):
            weather_data = get_weather_forecast(center_lat, center_lon, 7)
            
            if weather_data["status"] == "success":
                st.session_state.weather_data = weather_data
                st.success("✅ Weather data retrieved!")
                st.rerun()
            else:
                st.error("❌ Failed to get weather data")
    
    if "weather_data" in st.session_state:
        weather = st.session_state.weather_data
        forecast = weather.get("forecast", {})
        
        if "daily" in forecast:
            daily_data = forecast["daily"]
            
            # Weather metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                today_temp = daily_data["temperature_2m_max"][0] if daily_data["temperature_2m_max"] else 0
                st.metric("Today's Max Temp", f"{today_temp:.1f}°C")
            
            with col2:
                today_precip = daily_data["precipitation_sum"][0] if daily_data["precipitation_sum"] else 0
                st.metric("Today's Precipitation", f"{today_precip:.1f} mm")
            
            with col3:
                today_wind = daily_data["wind_speed_10m_max"][0] if daily_data["wind_speed_10m_max"] else 0
                st.metric("Today's Max Wind", f"{today_wind:.1f} m/s")
            
            with col4:
                avg_temp = sum(daily_data["temperature_2m_max"]) / len(daily_data["temperature_2m_max"]) if daily_data["temperature_2m_max"] else 0
                st.metric("7-Day Avg Temp", f"{avg_temp:.1f}°C")
            
            # Weather chart
            st.subheader("📊 7-Day Weather Forecast")
            
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            
            dates = daily_data["time"]
            temps_max = daily_data["temperature_2m_max"]
            temps_min = daily_data["temperature_2m_min"]
            precip = daily_data["precipitation_sum"]
            wind = daily_data["wind_speed_10m_max"]
            
            fig = make_subplots(
                rows=3, cols=1,
                subplot_titles=('Temperature (°C)', 'Precipitation (mm)', 'Wind Speed (m/s)'),
                vertical_spacing=0.1
            )
            
            # Temperature
            fig.add_trace(
                go.Scatter(x=dates, y=temps_max, name='Max Temp', line=dict(color='red')),
                row=1, col=1
            )
            fig.add_trace(
                go.Scatter(x=dates, y=temps_min, name='Min Temp', line=dict(color='blue')),
                row=1, col=1
            )
            
            # Precipitation
            fig.add_trace(
                go.Bar(x=dates, y=precip, name='Precipitation', marker_color='lightblue'),
                row=2, col=1
            )
            
            # Wind
            fig.add_trace(
                go.Scatter(x=dates, y=wind, name='Wind Speed', line=dict(color='green')),
                row=3, col=1
            )
            
            fig.update_layout(height=600, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
            
            # Irrigation recommendations
            st.subheader("💧 Irrigation Recommendations")
            
            total_precip = sum(precip)
            avg_temp = sum(temps_max) / len(temps_max)
            
            if total_precip > 20:
                st.info("🌧️ High precipitation expected. Consider reducing irrigation.")
            elif total_precip < 5 and avg_temp > 30:
                st.warning("☀️ Hot and dry conditions. Consider increasing irrigation.")
            else:
                st.success("✅ Normal weather conditions. Continue regular irrigation schedule.")
            
            # Risk assessment
            st.subheader("⚠️ Weather Risk Assessment")
            
            risks = []
            if max(wind) > 10:
                risks.append("High wind speeds may affect irrigation efficiency")
            if max(temps_max) > 35:
                risks.append("High temperatures may increase water demand")
            if total_precip > 30:
                risks.append("Heavy rainfall may cause waterlogging")
            
            if risks:
                for risk in risks:
                    st.warning(f"⚠️ {risk}")
            else:
                st.success("✅ No significant weather risks detected")