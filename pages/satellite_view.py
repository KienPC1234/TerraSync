"""
TerraSync Satellite View Page
Xem ruộng qua ảnh vệ tinh với AI upscaling
(Đã cập nhật để tương thích với API v1.1.0)
"""

import streamlit as st
import folium
from streamlit_folium import folium_static
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from typing import Dict, List, Any
from PIL import Image, ImageDraw
import io
import base64
from database import db
import time

# --- THÊM CÁC IMPORT MỚI ĐỂ XỬ LÝ NDVI GEO-TIFF ---
try:
    import numpy as np
    import rasterio
    from rasterio.io import MemoryFile
    from matplotlib import cm
    from matplotlib.colors import Normalize
except ImportError:
    st.error("Lỗi: Không tìm thấy thư viện. Vui lòng chạy: pip install rasterio numpy matplotlib")
    st.stop()
# --- KẾT THÚC THÊM IMPORT ---


API_URL = "http://172.24.193.209:9990" # Giữ nguyên API URL của bạn

# --- HÀM HELPER MỚI: CHUYỂN ĐỔI NDVI TIFF SANG PNG ĐỂ HIỂN THỊ ---
def convert_ndvi_to_png(geotiff_bytes: bytes) -> bytes:
    """
    Chuyển đổi file GeoTIFF NDVI (1 band, float) sang ảnh PNG (3 band, 8-bit)
    sử dụng colormap 'RdYlGn' (Red-Yellow-Green).
    """
    try:
        with MemoryFile(geotiff_bytes) as memfile:
            with memfile.open() as dataset:
                # Đọc band 1 (NDVI)
                ndvi_data = dataset.read(1).astype(np.float32)
                # Xử lý các giá trị no-data (nếu có)
                ndvi_data[ndvi_data == dataset.nodata] = np.nan
        
        # Chuẩn hóa giá trị NDVI từ -1 (Đỏ) đến 1 (Xanh)
        norm = Normalize(vmin=-1, vmax=1)
        
        # Áp dụng colormap 'RdYlGn'
        colormap = cm.get_cmap('RdYlGn')
        
        # Áp dụng colormap (bỏ qua giá trị nan)
        colored_data = colormap(norm(ndvi_data), bytes=True)
        
        # Tạo ảnh PIL từ mảng numpy (bỏ kênh Alpha)
        img = Image.fromarray(colored_data[:, :, :3], 'RGB')
        
        # Xử lý vùng 'nan' (no-data) thành màu đen trong suốt (nếu cần)
        # Ở đây ta để mặc định (thường là màu xám/trắng tùy colormap)
        
        # Lưu ảnh sang PNG
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
    
    except Exception as e:
        print(f"Lỗi chuyển đổi NDVI TIFF: {e}")
        # Tạo ảnh báo lỗi
        img = Image.new('RGB', (300, 200), color = 'white')
        d = ImageDraw.Draw(img)
        d.text((10,10), f"Lỗi xử lý NDVI TIFF:\n{e}", fill='red')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

# --- ĐÃ SỬA: Cập nhật hàm gọi API ---
def process_satellite_imagery(lat: float, lon: float, polygon: List[List[float]] = None) -> Dict[str, Any]:
    """
    Xử lý ảnh vệ tinh sử dụng API endpoint /process_satellite_image.
    (Đã cập nhật để tương thích với API v1.1.0)
    """
    coords = []
    
    if polygon is None or len(polygon) < 3:
        side = 0.001
        min_lat, max_lat = lat - side / 2, lat + side / 2
        min_lon, max_lon = lon - side / 2, lon + side / 2
        coords = [
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat]
        ]
    else:
        coords = [[p[1], p[0]] for p in polygon]

    # --- SỬA PAYLOAD: Bỏ 'upscale' và 'collection' ---
    payload = {
        "coords": coords,
        "cloud": 50.0,
        "days": 30, # Giữ nguyên 30 ngày (theo code cũ, không phải comment)
    }
    
    try:
        response = requests.post(
            f"{API_URL}/process_satellite_image",
            json=payload,
            timeout=60000 
        )
        
        if response.status_code == 200:
            api_result = response.json()
            
            # --- XÓA MOCK NDVI: API đã trả về dữ liệu thật ---
            
            # Trả về kết quả API đầy đủ
            return {
                "status": "success",
                "api_result": api_result
            }
        else:
            return {"status": "error", "message": f"API Error {response.status_code}: {response.text}"}
    except requests.exceptions.Timeout:
         return {"status": "error", "message": "API request timed out (quá 60000 giây)."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- HÀM NÀY GIỮ NGUYÊN ---
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

# --- HÀM NÀY GIỮ NGUYÊN ---
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

# --- ĐÃ SỬA: Cập nhật hàm render bản đồ ---
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
    
    # Tạo bản đồ (Giữ nguyên)
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=16,
        tiles=None
    )
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='Satellite',
        overlay=False,
        control=True
    ).add_to(m)
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
    folium.Marker(
        [center_lat, center_lon],
        popup=f"Center of {selected_field.get('name', 'Field')}",
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(m)
    folium_static(m, width=800, height=500)
    
    # Thông tin field (Giữ nguyên)
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
        if st.button("🛰️ Xem ruộng của bạn từ không gian!", type="primary", help="Lấy ảnh mới nhất trong vòng 30 ngày qua"):
            with st.spinner("🛰️ Đang kết nối với vệ tinh, tìm ảnh mới nhất và dùng AI xử lý... Quá trình này có thể mất vài phút."):
                
                result = process_satellite_imagery(center_lat, center_lon, selected_field.get('polygon'))
                
                if result["status"] == "success":
                    st.session_state.satellite_result = result
                    st.success("✅ Đã tải và xử lý ảnh vệ tinh thành công!")

                    # --- SỬA LỖI HIỂN THỊ ẢNH ---
                    api_res = result["api_result"]
                    # 1. Đổi 'image_base64' -> 'upscaled_image_base64'
                    if "upscaled_image_base64" in api_res:
                        image_bytes = base64.b64decode(api_res["upscaled_image_base64"])
                        
                        # 2. Lấy ngày chụp từ 'product_info' (nếu có)
                        product_info = api_res.get("product_info", {})
                        acquisition_date = product_info.get("acquisition_date", product_info.get("title", "Unknown Date"))

                        caption = f"Ảnh vệ tinh Sentinel-2 (AI Upscaled).\nDữ liệu được chụp: {acquisition_date}"
                        st.image(Image.open(io.BytesIO(image_bytes)), caption=caption, use_container_width=True)
                    # --- KẾT THÚC SỬA LỖI ---
                
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

# --- ĐÃ SỬA: Viết lại hoàn toàn tab NDVI ---

def render_ndvi_analysis():
    """Phân tích NDVI từ dữ liệu API mới + biểu đồ thống kê"""
    st.subheader("📊 NDVI (Normalized Difference Vegetation Index) Analysis")
    
    if "satellite_result" not in st.session_state:
        st.info("Vui lòng xử lý ảnh vệ tinh (process satellite imagery) ở tab 🗺️ Satellite Map trước.")
        return
    
    result = st.session_state.satellite_result
    api_res = result.get("api_result", {})

    # 1. Ảnh màu upscaled
    st.subheader("🖼️ AI Upscaled True-Color Image")
    if "upscaled_image_base64" in api_res:
        image_bytes = base64.b64decode(api_res["upscaled_image_base64"])
        st.image(Image.open(io.BytesIO(image_bytes)), caption="Ảnh màu AI Upscaled (để so sánh)", use_container_width=True)
    else:
        st.warning("Không tìm thấy ảnh màu upscaled.")

    # 2. Ảnh NDVI và phân tích thống kê
    st.subheader("🌱 NDVI (Vegetation Health) Image")
    ndvi_stats = None

    if "ndvi_geotiff_base64" in api_res:
        with st.spinner("Đang phân tích ảnh NDVI GeoTIFF..."):
            try:
                tiff_bytes = base64.b64decode(api_res["ndvi_geotiff_base64"])

                # Đọc NDVI từ GeoTIFF
                with rasterio.MemoryFile(tiff_bytes) as memfile:
                    with memfile.open() as dataset:
                        ndvi_data = dataset.read(1).astype(float)
                        ndvi_data = np.clip(ndvi_data, -1, 1)
                        ndvi_masked = ndvi_data[~np.isnan(ndvi_data)]

                # Chuyển NDVI sang ảnh PNG để hiển thị
                from matplotlib import cm
                colormap = cm.get_cmap('RdYlGn')
                ndvi_normalized = (ndvi_data + 1) / 2  # scale -1..1 → 0..1
                ndvi_rgb = (colormap(ndvi_normalized)[:, :, :3] * 255).astype(np.uint8)
                ndvi_img = Image.fromarray(ndvi_rgb)

                buf = io.BytesIO()
                ndvi_img.save(buf, format="PNG")
                st.image(buf.getvalue(), caption="Bản đồ NDVI (Đỏ = Đất trống/Nước, Xanh = Thực vật khỏe mạnh)", use_container_width=True)

                # Legend
                st.image("https://support.geoagro.com/wp-content/uploads/2021/04/en_NDVI-04.png",
                         caption="Chú thích NDVI: -1 (Đỏ) đến +1 (Xanh lá)", width="stretch")

                # Tính thống kê NDVI
                ndvi_stats = {
                    "mean": float(np.mean(ndvi_masked)),
                    "min": float(np.min(ndvi_masked)),
                    "max": float(np.max(ndvi_masked)),
                    "healthy_ratio": float(np.sum(ndvi_masked > 0.5) / len(ndvi_masked) * 100),
                    "moderate_ratio": float(np.sum((ndvi_masked > 0.2) & (ndvi_masked <= 0.5)) / len(ndvi_masked) * 100),
                    "low_ratio": float(np.sum(ndvi_masked <= 0.2) / len(ndvi_masked) * 100),
                }

                st.success(f"✅ NDVI trung bình: {ndvi_stats['mean']:.3f} | "
                           f"Thực vật khỏe mạnh: {ndvi_stats['healthy_ratio']:.1f}% | "
                           f"Trung bình: {ndvi_stats['moderate_ratio']:.1f}% | "
                           f"Yếu/kém: {ndvi_stats['low_ratio']:.1f}%")

                # Biểu đồ Histogram
                fig, ax = plt.subplots()
                ax.hist(ndvi_masked, bins=30, color='green', alpha=0.7)
                ax.set_title("Phân bố giá trị NDVI")
                ax.set_xlabel("Giá trị NDVI (-1 đến +1)")
                ax.set_ylabel("Số lượng pixel")
                st.pyplot(fig)

                # Biểu đồ Pie chart phần trăm sức khỏe
                fig2, ax2 = plt.subplots()
                labels = ['🌿 Khỏe mạnh (>0.5)', '🌾 Trung bình (0.2–0.5)', '🪵 Yếu/kém (≤0.2)']
                sizes = [ndvi_stats["healthy_ratio"], ndvi_stats["moderate_ratio"], ndvi_stats["low_ratio"]]
                ax2.pie(sizes, labels=labels, autopct='%1.1f%%', colors=['#00cc44', '#ccff66', '#ff6666'])
                ax2.set_title("Tỷ lệ diện tích theo mức NDVI")
                st.pyplot(fig2)

            except Exception as e:
                st.error(f"Không thể xử lý ảnh NDVI GeoTIFF: {e}")
    else:
        st.warning("Không tìm thấy dữ liệu NDVI GeoTIFF trong kết quả API.")

    # 3. Thông tin ảnh vệ tinh
    st.subheader("📊 Image Metrics")
    col1, col2 = st.columns(2)
    product_info = api_res.get("product_info", {})

    with col1:
        coords = api_res.get('top_left_lonlat', ['N/A', 'N/A'])
        lat_str = f"{coords[1]:.5f}" if isinstance(coords[1], float) else "N/A"
        lon_str = f"{coords[0]:.5f}" if isinstance(coords[0], float) else "N/A"
        st.metric("Top-Left (Lon, Lat)", f"{lon_str}, {lat_str}")

    with col2:
        coords = api_res.get('bottom_right_lonlat', ['N/A', 'N/A'])
        lat_str = f"{coords[1]:.5f}" if isinstance(coords[1], float) else "N/A"
        lon_str = f"{coords[0]:.5f}" if isinstance(coords[0], float) else "N/A"
        st.metric("Bottom-Right (Lon, Lat)", f"{lon_str}, {lat_str}")
        
    # 4. Xem thông tin sản phẩm
    with st.expander("🔬 Xem thông tin sản phẩm (Product Info) từ API"):
        st.json(product_info)

# --- HÀM NÀY GIỮ NGUYÊN ---
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

# --- Hàm main (để chạy file này độc lập nếu cần) ---
# Thông thường, bạn sẽ import `render_satellite_view` vào trang chính.
if __name__ == "__main__":
    # Cấu hình giả lập (mock) user và db nếu chạy độc lập
    if not hasattr(st, 'user'):
        from collections import namedtuple
        MockUser = namedtuple("MockUser", ["email", "is_logged_in"])
        st.user = MockUser(email="test@example.com", is_logged_in=True)
        
        # Mock DB
        class MockDB:
            def get_user_fields(self, email):
                return [
                    {
                        "name": "Thửa ruộng 1",
                        "crop": "Lúa",
                        "area": 1.5,
                        "center": [20.450123, 106.325678],
                        "polygon": [
                            [20.449, 106.325],
                            [20.451, 106.325],
                            [20.451, 106.327],
                            [20.449, 106.327]
                        ]
                    }
                ]
        db = MockDB()

    render_satellite_view()