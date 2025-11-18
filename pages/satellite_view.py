import streamlit as st
import folium
from streamlit_folium import folium_static
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any
from PIL import Image, ImageDraw
import io
import base64
from database import db
from utils import fetch_forecast
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go

try:
    import numpy as np
    from rasterio.io import MemoryFile
    from matplotlib import cm
    from matplotlib.colors import Normalize
except ImportError:
    st.error("Lỗi: Không tìm thấy thư viện. Vui lòng chạy: "
             "pip install rasterio numpy matplotlib")
    st.stop()

API_URL = "http://172.24.193.209:9990"


def convert_ndvi_to_png(geotiff_bytes: bytes) -> bytes:
    try:
        with MemoryFile(geotiff_bytes) as memfile:
            with memfile.open() as dataset:
                ndvi_data = dataset.read(1).astype(np.float32)
                ndvi_data[ndvi_data == dataset.nodata] = np.nan

        norm = Normalize(vmin=-1, vmax=1)
        colormap = cm.get_cmap('RdYlGn')
        colored_data = colormap(norm(ndvi_data), bytes=True)
        img = Image.fromarray(colored_data[:, :, :3], 'RGB')

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    except Exception as e:
        print(f"Lỗi chuyển đổi NDVI TIFF: {e}")
        img = Image.new('RGB', (300, 200), color='white')
        d = ImageDraw.Draw(img)
        d.text((10, 10), f"Lỗi xử lý NDVI TIFF:\n{e}", fill='red')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()


def process_satellite_imagery(lat: float, lon: float,
                              polygon: List[List[float]] = None
                              ) -> Dict[str, Any]:
    coords = []

    if polygon is None or len(polygon) < 3:
        side = 0.001
        min_lat, max_lat = lat - side / 2, lat + side / 2
        min_lon, max_lon = lon - side / 2, lon + side / 2
        coords = [[min_lon, min_lat], [max_lon, min_lat],
                  [max_lon, max_lat], [min_lon, max_lat]]
    else:
        coords = [[p[1], p[0]] for p in polygon]

    payload = {"coords": coords, "cloud": 50.0, "days": 30}

    try:
        response = requests.post(f"{API_URL}/process_satellite_image",
                                 json=payload, timeout=60000)
        response.raise_for_status()
        return {"status": "success", "api_result": response.json()}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Lỗi API: {e}"}


def render_satellite_view():
    st.title("🛰️ Chế độ xem Vệ tinh & Viễn thám")
    st.markdown("Xem ruộng của bạn từ không gian với ảnh vệ tinh "
                "Sentinel-2 và AI.")

    tab1, tab2, tab3 = st.tabs(["🗺️ Bản đồ vệ tinh",
                                "📊 Phân tích NDVI",
                                "🌤️ Lớp phủ thời tiết"])

    with tab1:
        render_satellite_map()
    with tab2:
        render_ndvi_analysis()
    with tab3:
        render_weather_overlay()


def render_satellite_map():
    st.subheader("🗺️ Bản đồ vệ tinh tương tác")

    if hasattr(st, 'user') and st.user.is_logged_in:
        user_fields = db.get("fields", {"user_email": st.user.email})
    else:
        user_fields = []

    if not user_fields:
        st.warning("Không tìm thấy vườn nào. Vui lòng thêm vườn trước.")
        return

    field_options = {f"{field.get('name', 'Không tên')} "
                     f"({field.get('crop', 'Không xác định')})": field
                     for field in user_fields}
    selected_field_name = st.selectbox("Chọn Vườn",
                                       options=list(field_options.keys()))
    selected_field = field_options[selected_field_name]

    center_lat = selected_field.get('center', [20.450123, 106.325678])[0]
    center_lon = selected_field.get('center', [20.450123, 106.325678])[1]

    m = folium.Map(
        location=[
            center_lat,
            center_lon],
        zoom_start=16,
        tiles=None)
    folium.TileLayer(tiles='OpenStreetMap', name='Vệ tinh',
                     overlay=False, control=True).add_to(m)
    if 'polygon' in selected_field:
        folium.Polygon(
            locations=selected_field['polygon'],
            popup=(f"Vườn: {selected_field.get('name', 'Không tên')}<br>"
                   f"Cây trồng: {selected_field.get('crop', 'Không xác định')}"
                   f"<br>Diện tích: {selected_field.get('area', 0):.2f} ha"),
            color='red', weight=3, fillColor='yellow', fillOpacity=0.3
        ).add_to(m)
    folium.Marker([center_lat, center_lon],
                  popup=f"Tâm của {selected_field.get('name', 'Vườn')}",
                  icon=folium.Icon(color='red', icon='info-sign')).add_to(m)
    folium_static(m, width=800, height=500)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Diện tích vườn", f"{selected_field.get('area', 0):.2f} ha")
    with col2:
        st.metric("Loại cây trồng",
                  selected_field.get('crop', 'Không xác định'))
    with col3:
        st.metric("Tọa độ", f"{center_lat:.6f}, {center_lon:.6f}")

    st.subheader("🤖 Xử lý vệ tinh bằng AI")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("Nhận ảnh vệ tinh **mới nhất** từ **Sentinel-2** "
                    "của Cơ quan Vũ trụ Châu Âu (ESA).")
        if st.button("🛰️ Xem ruộng của bạn từ không gian!", type="primary",
                     help="Lấy ảnh mới nhất trong vòng 30 ngày qua"):
            with st.spinner("🛰️ Đang kết nối với vệ tinh, tìm ảnh mới nhất..."):
                result = process_satellite_imagery(
                    center_lat, center_lon, selected_field.get('polygon'))

                if result["status"] == "success":
                    st.session_state.satellite_result = result
                    st.success("✅ Đã tải và xử lý ảnh vệ tinh thành công!")

                    api_res = result["api_result"]
                    if "upscaled_image_base64" in api_res:
                        image_bytes = base64.b64decode(
                            api_res["upscaled_image_base64"])
                        product_info = api_res.get("product_info", {})
                        acq_date = product_info.get(
                            "acquisition_date",
                            product_info.get("title", "Ngày không xác định"))
                        caption = (
                            f"Ảnh vệ tinh Sentinel-2 (AI Upscaled).\n"
                            f"Dữ liệu được chụp: {acq_date}"
                        )
                        st.image(Image.open(io.BytesIO(image_bytes)),
                                 caption=caption, use_container_width=True)
                else:
                    st.error(f"❌ Xử lý thất bại: "
                             f"{result.get('message', 'Lỗi không xác định')}")

    with col2:
        st.date_input("Chọn khoảng thời gian",
                      value=(datetime.now() - timedelta(days=7),
                             datetime.now()),
                      max_value=datetime.now())
        if st.button("📅 Lấy dữ liệu lịch sử"):
            st.info("Dữ liệu vệ tinh lịch sử sẽ được lấy ở đây")


def render_ndvi_analysis():
    st.subheader("📊 Phân tích NDVI (Chỉ số thực vật chênh lệch chuẩn hóa)")

    if "satellite_result" not in st.session_state:
        st.info("Vui lòng xử lý ảnh vệ tinh ở tab 🗺️ Bản đồ vệ tinh trước.")
        return

    result = st.session_state.satellite_result
    api_res = result.get("api_result", {})

    st.subheader("🖼️ Ảnh màu thực AI Upscaled")
    if "upscaled_image_base64" in api_res:
        image_bytes = base64.b64decode(api_res["upscaled_image_base64"])
        st.image(Image.open(io.BytesIO(image_bytes)),
                 caption="Ảnh màu AI Upscaled (để so sánh)",
                 use_container_width=True)
    else:
        st.warning("Không tìm thấy ảnh màu upscaled.")

    st.subheader("🌱 Ảnh NDVI (Sức khỏe thực vật)")
    if "ndvi_geotiff_base64" in api_res:
        with st.spinner("Đang phân tích ảnh NDVI GeoTIFF..."):
            try:
                tiff_bytes = base64.b64decode(api_res["ndvi_geotiff_base64"])
                png_bytes = convert_ndvi_to_png(tiff_bytes)
                st.image(png_bytes,
                         caption="Bản đồ NDVI (Đỏ = Đất trống/Nước, "
                                 "Xanh = Thực vật khỏe mạnh)",
                         use_container_width=True)
                st.image("https://support.geoagro.com/wp-content/uploads/"
                         "2021/04/en_NDVI-04.png",
                         caption="Chú thích NDVI: -1 (Đỏ) đến +1 (Xanh lá)",
                         width=300)
            except Exception as e:
                st.error(f"Không thể xử lý ảnh NDVI GeoTIFF: {e}")
    else:
        st.warning("Không tìm thấy dữ liệu NDVI GeoTIFF trong kết quả API.")


def render_weather_overlay():
    st.subheader("🌤️ Lớp phủ thời tiết")

    if hasattr(st, 'user') and st.user.is_logged_in:
        user_fields = db.get("fields", {"user_email": st.user.email})
    else:
        user_fields = []

    if not user_fields:
        st.warning("Không tìm thấy vườn nào. Vui lòng thêm vườn trước.")
        return

    field_options = {f"{field.get('name', 'Không tên')} "
                     f"({field.get('crop', 'Không xác định')})": field
                     for field in user_fields}
    selected_field_name = st.selectbox("Chọn Vườn cho Thời tiết",
                                       options=list(field_options.keys()),
                                       key="weather_field")
    selected_field = field_options[selected_field_name]

    center_lat = selected_field.get('center', [20.450123, 106.325678])[0]
    center_lon = selected_field.get('center', [20.450123, 106.325678])[1]

    if st.button("🌤️ Lấy dự báo thời tiết"):
        with st.spinner("Đang lấy dữ liệu thời tiết..."):
            weather_data = fetch_forecast(center_lat, center_lon)

            if weather_data:
                st.session_state.weather_data = weather_data
                st.success("✅ Đã lấy dữ liệu thời tiết!")
                st.rerun()
            else:
                st.error("❌ Không thể lấy dữ liệu thời tiết")

    if "weather_data" in st.session_state:
        weather = st.session_state.weather_data
        df = pd.DataFrame(weather)
        df['time'] = pd.to_datetime(df['time'])

        st.subheader("📊 Dự báo thời tiết 7 ngày")

        fig = make_subplots(rows=3, cols=1,
                            subplot_titles=('Nhiệt độ (°C)',
                                            'Lượng mưa (mm)',
                                            'Tốc độ gió (m/s)'),
                            vertical_spacing=0.1)

        fig.add_trace(go.Scatter(x=df['time'], y=df['temperature'],
                                 name='Nhiệt độ'), row=1, col=1)
        fig.add_trace(go.Bar(x=df['time'], y=df['precipitation'],
                             name='Lượng mưa'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df['time'], y=df['wind_speed'],
                                 name='Tốc độ gió'), row=3, col=1)

        fig.update_layout(height=600, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("💧 Khuyến nghị tưới tiêu")

        total_precip = df['precipitation'].sum()
        avg_temp = df['temperature'].mean()

        if total_precip > 20:
            st.info("🌧️ Dự kiến có mưa nhiều. Cân nhắc giảm tưới.")
        elif total_precip < 5 and avg_temp > 30:
            st.warning("☀️ Điều kiện nóng và khô. Cân nhắc tăng tưới.")
        else:
            st.success("✅ Điều kiện thời tiết bình thường. "
                       "Tiếp tục lịch tưới tiêu thông thường.")

        st.subheader("⚠️ Đánh giá rủi ro thời tiết")

        risks = []
        if df['wind_speed'].max() > 10:
            risks.append("Tốc độ gió cao có thể ảnh hưởng đến hiệu quả tưới")
        if df['temperature'].max() > 35:
            risks.append("Nhiệt độ cao có thể làm tăng nhu cầu nước")
        if total_precip > 30:
            risks.append("Mưa lớn có thể gây ngập úng")

        if risks:
            for risk in risks:
                st.warning(f"⚠️ {risk}")
        else:
            st.success("✅ Không phát hiện rủi ro thời tiết đáng kể")


