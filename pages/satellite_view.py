import streamlit as st
import folium
from streamlit_folium import folium_static
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from PIL import Image, ImageDraw
import io
import base64
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import plotly.express as px
import matplotlib.pyplot as plt
from matplotlib import cm, colors

# Giả lập database/utils nếu bạn chạy độc lập, hãy giữ nguyên import của bạn
from database import db
from utils import fetch_forecast, get_weather_recommendation

try:
    import numpy as np
    from rasterio.io import MemoryFile
    import rasterio.mask
    from matplotlib import cm
    from matplotlib.colors import Normalize
except ImportError:
    st.error("Lỗi: Thiếu thư viện xử lý ảnh. Vui lòng chạy: "
             "pip install rasterio numpy matplotlib plotly pandas")
    st.stop()

API_URL = "http://172.24.193.209:9990"

WMO_WEATHER_CODES = {
    0: ("☀️", "Trời quang"), 1: ("🌤️", "Nắng nhẹ"), 2: ("⛅", "Nhiều mây"), 3: ("☁️", "U ám"),
    45: ("🌫️", "Sương mù"), 48: ("🌫️", "Sương mù dày"),
    51: ("🌦️", "Mưa phùn nhẹ"), 53: ("🌦️", "Mưa phùn vừa"), 55: ("🌦️", "Mưa phùn dày"),
    56: ("🌨️", "Mưa băng"), 57: ("🌨️", "Mưa băng dày"),
    61: ("🌧️", "Mưa nhẹ"), 63: ("🌧️", "Mưa vừa"), 65: ("🌧️", "Mưa to"),
    66: ("🌨️", "Mưa tuyết"), 67: ("🌨️", "Mưa tuyết dày"),
    71: ("❄️", "Tuyết rơi nhẹ"), 73: ("❄️", "Tuyết rơi vừa"), 75: ("❄️", "Tuyết rơi dày"),
    77: ("❄️", "Hạt tuyết"),
    80: ("⛈️", "Mưa rào nhẹ"), 81: ("⛈️", "Mưa rào vừa"), 82: ("⛈️", "Mưa rào to"),
    85: ("🌨️", "Tuyết"), 86: ("🌨️", "Tuyết nhiều"),
    95: ("🌩️", "Dông"), 96: ("🌩️", "Dông mưa đá nhẹ"), 99: ("🌩️", "Dông mưa đá mạnh")
}


# --- HELPER FUNCTIONS CHO XỬ LÝ ẢNH & DỮ LIỆU ---

def process_ndvi_data(geotiff_bytes: bytes, polygon: List[List[float]] = None) -> Tuple[Image.Image, np.ndarray, float]:
    """
    Xử lý bytes GeoTIFF để trả về:
    1. Ảnh PNG màu (RGBA - có trong suốt) để hiển thị đẹp trên Web/App
    2. Mảng Numpy thô (để vẽ biểu đồ/thống kê)
    3. Giá trị NoData
    """
    try:
        with MemoryFile(geotiff_bytes) as memfile:
            with memfile.open() as dataset:
                nodata_val = dataset.nodata
                
                if polygon:
                    # Polygon is [[lat, lon], ...] (Folium format)
                    # Rasterio/GeoJSON expects [[lon, lat], ...]
                    roi_coords = [[p[1], p[0]] for p in polygon]
                    shapes = [{'type': 'Polygon', 'coordinates': [roi_coords]}]
                    
                    try:
                        # Crop=True removes rows/cols outside the bounding box
                        # Nodata handling: fill outside with existing nodata or NaN
                        fill_val = nodata_val if nodata_val is not None else np.nan
                        masked_data, _ = rasterio.mask.mask(dataset, shapes, crop=True, nodata=fill_val)
                        ndvi_data = masked_data[0]
                        
                        # If we used NaN as fill, ensure nodata_val reflects that for later masking
                        if nodata_val is None:
                            nodata_val = np.nan
                    except Exception as e:
                        print(f"Lỗi cắt ảnh theo polygon: {e}")
                        ndvi_data = dataset.read(1)
                else:
                    # Đọc band 1
                    ndvi_data = dataset.read(1)
                
                # Chuyển sang float để tính toán
                ndvi_float = ndvi_data.astype(np.float32)

                # 1. Tạo Mask cho dữ liệu không hợp lệ (Nodata hoặc NaN)
                if nodata_val is not None:
                    if np.isnan(nodata_val):
                        mask = np.isnan(ndvi_float)
                    else:
                        mask = (ndvi_float == nodata_val) | np.isnan(ndvi_float)
                else:
                    mask = np.isnan(ndvi_float)
                
                # Gán NaN cho các vùng masked để không ảnh hưởng thống kê sau này
                analysis_data = ndvi_float.copy()
                analysis_data[mask] = np.nan

                # 2. Chuẩn bị dữ liệu hiển thị (Visualization)
                # Dữ liệu NDVI luôn nằm trong khoảng -1 đến 1
                norm = colors.Normalize(vmin=-1.0, vmax=1.0)
                
                # Sử dụng colormap chuẩn cho NDVI: RdYlGn (Đỏ - Vàng - Xanh)
                # Đỏ/Nâu: Đất trống/Cây yếu (-1 đến 0)
                # Vàng: Cây mới lớn (0 đến 0.3)
                # Xanh: Cây khỏe mạnh (0.3 đến 1)
                cmap = plt.get_cmap('RdYlGn')

                # Áp dụng colormap -> tạo ra mảng (H, W, 4) chứa RGBA (0-1 float hoặc 0-255 int)
                # cmap(norm(data)) trả về giá trị RGBA float 0-1
                # Chúng ta dùng masked array để matplotlib tự động xử lý vùng bad
                masked_ndvi = np.ma.masked_where(mask, ndvi_float)
                
                # Chuyển đổi sang RGBA (bytes=True trả về 0-255 uint8)
                rgba_img = cmap(norm(masked_ndvi), bytes=True) 

                # 3. Xử lý trong suốt (Transparency)
                # Tại những vị trí mask bị True (là nodata), gán Alpha (kênh 3) = 0
                rgba_img[mask, 3] = 0

                # Tạo ảnh PIL từ array RGBA
                img = Image.fromarray(rgba_img, 'RGBA')
                
                return img, analysis_data, nodata_val

    except Exception as e:
        print(f"Lỗi xử lý dữ liệu NDVI: {e}")
        # Trả về ảnh rỗng trong suốt nếu lỗi
        return Image.new('RGBA', (100, 100), (0, 0, 0, 0)), np.array([]), 0

def classify_ndvi(value):
    """Phân loại sức khỏe dựa trên chỉ số NDVI"""
    if np.isnan(value): return "Không xác định"
    if value < 0.1: return "Đất trống / Nước"
    if value < 0.2: return "Thực vật rất thưa / Căng thẳng"
    if value < 0.4: return "Thực vật thưa / Đang phát triển"
    if value < 0.6: return "Sức khỏe trung bình"
    return "Sức khỏe rất tốt / Dày đặc"

def process_satellite_imagery(lat: float, lon: float, polygon: List[List[float]] = None) -> Dict[str, Any]:
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

# --- GIAO DIỆN CHÍNH ---

def render_satellite_view():
    st.title("🛰️ Giám Sát Mùa Màng Thông Minh")
    st.markdown("Theo dõi sức khỏe cây trồng từ vệ tinh Sentinel-2 kết hợp AI Deep Learning.")

    # CSS tùy chỉnh để làm đẹp các metrics
    st.markdown("""
    <style>
    [data-testid="stMetricValue"] {
        font-size: 24px;
        color: #006400;
    }
    .daily-forecast {
        text-align: center;
    }
    .day-name {
        font-weight: bold;
        font-size: 1.1em;
    }
    .weather-icon {
        font-size: 2.5em;
        line-height: 1;
    }
    </style>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["🗺️ Bản đồ & Ảnh Vệ Tinh", 
                                "📈 Phân Tích Sức Khỏe (NDVI)", 
                                "🌤️ Thời Tiết & Khuyến Nghị"])

    with tab1:
        render_satellite_map()
    with tab2:
        render_ndvi_analysis()
    with tab3:
        render_weather_overlay()

def render_satellite_map():
    st.subheader("🗺️ Vị trí & Thu thập dữ liệu")

    if hasattr(st, 'user') and st.user.is_logged_in:
        user_fields = db.get("fields", {"user_email": st.user.email})
    else:
        # Mock data để test nếu chưa login
        user_fields = []

    if not user_fields:
        st.warning("⚠️ Bạn chưa có vườn nào. Vui lòng thêm vườn trong phần quản lý.")
        return

    col_sel1, col_sel2 = st.columns([2, 1])
    with col_sel1:
        field_options = {f"{field.get('name', 'Không tên')} ({field.get('crop', 'Unknown')})": field for field in user_fields}
        selected_field_name = st.selectbox("Chọn khu vực giám sát", options=list(field_options.keys()))
        selected_field = field_options[selected_field_name]

    center_lat = selected_field.get('center', [20.45, 106.32])[0]
    center_lon = selected_field.get('center', [20.45, 106.32])[1]

    # Hiển thị bản đồ
    m = folium.Map(location=[center_lat, center_lon], zoom_start=16, tiles='OpenStreetMap')
    folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', 
                     attr='Esri', name='Vệ tinh (Esri)').add_to(m)
    
    if 'polygon' in selected_field:
        folium.Polygon(
            locations=selected_field['polygon'],
            popup=f"Diện tích: {selected_field.get('area', 0):.2f} ha",
            color='#FFD700', weight=2, fill=True, fillOpacity=0.1
        ).add_to(m)
    
    folium_static(m, width=800, height=400)

    # Nút hành động
    st.divider()
    col_act1, col_act2 = st.columns([1, 2])
    
    with col_act1:
        st.info("📡 **Dữ liệu trực tiếp**")
        crop_option = st.checkbox("Chỉ phân tích trong vùng chọn", value=True, help="Cắt ảnh và số liệu thống kê chính xác theo ranh giới vườn.")
        process_btn = st.button("🚀 Quét Vệ Tinh Ngay", type="primary", use_container_width=True)
    
    with col_act2:
        st.write(f"**Khu vực:** {selected_field.get('name')} | **Cây trồng:** {selected_field.get('crop')}")
        st.write("Hệ thống sẽ tìm ảnh rõ nét nhất (ít mây) trong 30 ngày qua.")

    if process_btn:
        with st.spinner("🛰️ Đang kết nối vệ tinh Sentinel-2 và xử lý AI... (Vui lòng chờ 10-20s)"):
            result = process_satellite_imagery(center_lat, center_lon, selected_field.get('polygon'))
            
            if result["status"] == "success":
                st.session_state.satellite_result = result
                st.session_state.selected_polygon = selected_field.get('polygon')
                st.session_state.crop_to_polygon = crop_option
                st.success("✅ Đã tải dữ liệu thành công! Chuyển sang tab 'Phân Tích Sức Khỏe' để xem chi tiết.")
            else:
                st.error(f"❌ Lỗi: {result.get('message')}")

def render_ndvi_analysis():
    st.header("📈 Phân Tích Chỉ Số Thực Vật (NDVI)")
    
    if "satellite_result" not in st.session_state:
        st.info("👋 Vui lòng quay lại tab **Bản đồ** và nhấn nút **'Quét Vệ Tinh Ngay'** trước.")
        return

    result = st.session_state.satellite_result
    api_res = result.get("api_result", {})
    
    # Lấy thông tin crop từ session state (đã lưu lúc bấm nút Quét)
    use_crop = st.session_state.get("crop_to_polygon", False)
    polygon_coords = st.session_state.get("selected_polygon", None)

    # Layout: Chia thành 2 cột chính
    col_visual, col_stats = st.columns([1.2, 1])

    # --- CỘT TRÁI: HÌNH ẢNH ---
    with col_visual:
        st.subheader("👁️ Trực quan hóa")
        tab_img1, tab_img2 = st.tabs(["🌱 Bản đồ NDVI", "📷 Ảnh Thực Tế"])
        
        ndvi_array = None
        
        with tab_img1:
            if "ndvi_geotiff_base64" in api_res:
                tiff_bytes = base64.b64decode(api_res["ndvi_geotiff_base64"])
                
                # Truyền polygon vào nếu có chọn crop
                crop_poly = polygon_coords if use_crop else None
                img_ndvi, ndvi_array, _ = process_ndvi_data(tiff_bytes, crop_poly)
                
                st.image(img_ndvi, use_container_width=True, caption="Vùng xanh đậm: Cây khỏe mạnh")
            else:
                st.warning("Không có dữ liệu NDVI.")

        with tab_img2:
            if "upscaled_image_base64" in api_res:
                rgb_bytes = base64.b64decode(api_res["upscaled_image_base64"])
                st.image(Image.open(io.BytesIO(rgb_bytes)), use_container_width=True, caption="Ảnh màu thực (AI Upscaled)")
            else:
                st.warning("Không có ảnh màu.")

    # --- CỘT PHẢI: SỐ LIỆU & BIỂU ĐỒ ---
    with col_stats:
        st.subheader("📊 Số liệu chi tiết")
        
        if ndvi_array is not None and ndvi_array.size > 0:
            # 1. Tính toán thống kê
            valid_ndvi = ndvi_array[~np.isnan(ndvi_array)]
            avg_ndvi = np.mean(valid_ndvi)
            max_ndvi = np.max(valid_ndvi)
            
            # Đánh giá tổng quan
            health_status = "Rất tốt" if avg_ndvi > 0.6 else "Trung bình" if avg_ndvi > 0.4 else "Cần chú ý"
            health_color = "green" if avg_ndvi > 0.6 else "orange" if avg_ndvi > 0.4 else "red"

            # Hiển thị Metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("NDVI Trung bình", f"{avg_ndvi:.2f}")
            m2.metric("NDVI Cao nhất", f"{max_ndvi:.2f}")
            m3.markdown(f"**Trạng thái:** :{health_color}[{health_status}]")

            # 2. Phân loại diện tích (Histogram Data)
            df_hist = pd.DataFrame({'NDVI': valid_ndvi})
            
            # Tạo phân loại cho Pie Chart
            conditions = [
                (df_hist['NDVI'] < 0.1),
                (df_hist['NDVI'] >= 0.1) & (df_hist['NDVI'] < 0.4),
                (df_hist['NDVI'] >= 0.4)
            ]
            choices = ['Đất trống/Nước', 'Cây thưa/Yếu', 'Cây khỏe mạnh']
            df_hist['Category'] = np.select(conditions, choices, default='Không xác định')
            
            pie_data = df_hist['Category'].value_counts().reset_index()
            pie_data.columns = ['Loại', 'Số lượng pixels']

            # 3. Vẽ biểu đồ Pie Chart (Tỷ lệ diện tích)
            fig_pie = px.pie(pie_data, values='Số lượng pixels', names='Loại', 
                             title='Tỷ lệ phân bố sức khỏe',
                             color='Loại',
                             color_discrete_map={
                                 'Đất trống/Nước': '#d62728',
                                 'Cây thưa/Yếu': '#ff7f0e', 
                                 'Cây khỏe mạnh': '#2ca02c'
                             },
                             hole=0.4)
            fig_pie.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=250)
            st.plotly_chart(fig_pie, use_container_width=True)

            # 4. Vẽ biểu đồ Histogram (Phân bố giá trị)
            fig_hist = px.histogram(df_hist, x="NDVI", nbins=30, 
                                    title="Phân bố chi tiết chỉ số NDVI",
                                    labels={'NDVI': 'Giá trị NDVI'},
                                    color_discrete_sequence=['#00CC96'])
            fig_hist.add_vline(x=avg_ndvi, line_dash="dash", line_color="red", annotation_text="TB")
            fig_hist.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=200, showlegend=False)
            st.plotly_chart(fig_hist, use_container_width=True)

        else:
            st.info("Đang chờ dữ liệu để phân tích...")

    # --- PHẦN GIẢI THÍCH Ý NGHĨA ---
    with st.expander("ℹ️ Hướng dẫn đọc chỉ số NDVI", expanded=False):
        st.markdown("""
        - **Dưới 0.1 (Màu đỏ/nâu):** Thường là đất trống, nước, bê tông hoặc cây đã chết.
        - **0.2 - 0.4 (Màu vàng/cam):** Cây mới trồng, cây bụi thưa hoặc cây đang bị bệnh/thiếu nước.
        - **0.5 - 0.8 (Màu xanh lá):** Cây trồng phát triển tốt, mật độ lá dày, quang hợp mạnh.
        """)

def render_daily_forecast(daily_df: pd.DataFrame):
    st.subheader("🗓️ Dự báo tổng quan 7 ngày")
    cols = st.columns(7)
    for i, day in daily_df.iterrows():
        with cols[i]:
            with st.container(border=True):
                day_name = day['time'].strftime('%a') # Mon, Tue
                icon, desc = WMO_WEATHER_CODES.get(day['weather_code'], ("❓", "Không rõ"))
                st.markdown(f"<div class='daily-forecast day-name'>{day_name}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='daily-forecast weather-icon'>{icon}</div>", unsafe_allow_html=True)
                st.metric("Nhiệt độ", f"{int(day['temperature_2m_max'])}°C")
                st.caption(f"Thấp: {int(day['temperature_2m_min'])}°C")
                st.caption(f"Mưa: {day['precipitation_sum']:.1f} mm")


def render_hourly_charts(hourly_df: pd.DataFrame):
    st.subheader("📊 Biểu đồ chi tiết (48 giờ tới)")
    df = hourly_df.head(48)

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        subplot_titles=("Nhiệt độ & Độ ẩm", "Lượng mưa", "Sức gió"),
        specs=[[{"secondary_y": True}], [{}], [{}]])

    # Nhiệt độ & Độ ẩm
    fig.add_trace(go.Scatter(x=df['time'], y=df['temperature_2m'], name="Nhiệt độ",
                             line=dict(color='orange')), row=1, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=df['time'], y=df['apparent_temperature'], name="Nhiệt độ cảm nhận",
                             line=dict(color='red', dash='dot')), row=1, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=df['time'], y=df['relative_humidity_2m'], name="Độ ẩm"),
                  row=1, col=1, secondary_y=True)

    # Lượng mưa
    fig.add_trace(go.Bar(x=df['time'], y=df['precipitation'], name="Lượng mưa (mm)",
                         marker_color='blue'), row=2, col=1)

    # Sức gió
    fig.add_trace(go.Scatter(x=df['time'], y=df['wind_speed_10m'], name="Tốc độ gió (km/h)",
                              line=dict(color='gray')), row=3, col=1)

    fig.update_layout(height=600, showlegend=False)
    fig.update_yaxes(title_text="Nhiệt độ (°C)", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Độ ẩm (%)", row=1, col=1, secondary_y=True, range=[0, 100])
    fig.update_yaxes(title_text="Lượng mưa (mm)", row=2, col=1)
    fig.update_yaxes(title_text="Tốc độ gió (km/h)", row=3, col=1)
    st.plotly_chart(fig, use_container_width=True)


def render_weather_overlay():
    st.header("🌤️ Thời Tiết & Canh Tác Thông Minh")

    if not (hasattr(st, 'user') and st.user.is_logged_in):
        st.warning("⚠️ Vui lòng đăng nhập để sử dụng tính năng này.")
        return
        
    user_fields = db.get("fields", {"user_email": st.user.email})

    if not user_fields:
        st.warning("Vui lòng thêm một vườn trong phần Quản lý Vườn trước.")
        return

    field_options = {f"{field.get('name')}": field for field in user_fields}
    selected_name = st.selectbox("Chọn khu vực để xem dự báo & nhận khuyến nghị:", list(field_options.keys()), key="w_select")
    selected_field = field_options[selected_name]
    
    lat, lon = selected_field.get('center', [20.0, 105.0])
    
    # Reset states if field changes
    field_id = selected_field.get('id')
    if st.session_state.get('weather_field_id') != field_id:
        st.session_state.pop('weather_data', None)
        st.session_state.pop('ai_weather_recommendation', None)
        st.session_state['weather_field_id'] = field_id

    if st.button("🔄 Cập nhật Thời Tiết & Nhận Khuyến Nghị AI", type="primary", use_container_width=True):
        with st.spinner("Đang tải dữ liệu khí tượng và phân tích AI..."):
            weather_data = fetch_forecast(lat, lon)
            if weather_data:
                st.session_state.weather_data = weather_data
                # Force clear old recommendation to get a new one, but don't rerun
                st.session_state.pop('ai_weather_recommendation', None) 
            else:
                st.error("Không thể tải được dữ liệu thời tiết. Vui lòng thử lại.")

    if "weather_data" in st.session_state:
        weather_data = st.session_state.weather_data
        
        # Get AI recommendation if not already present
        if 'ai_weather_recommendation' not in st.session_state:
            with st.spinner("🤖 CropNet AI đang phân tích thời tiết..."):
                recommendation = get_weather_recommendation(selected_field, weather_data)
                st.session_state.ai_weather_recommendation = recommendation
        
        with st.expander("🤖 **Phân Tích & Khuyến Nghị từ CropNet AI**", expanded=True):
            st.markdown(st.session_state.get('ai_weather_recommendation', "Không có khuyến nghị."))

        st.divider()
        
        render_daily_forecast(weather_data['daily'])
        
        st.divider()
        
        render_hourly_charts(weather_data['hourly'])