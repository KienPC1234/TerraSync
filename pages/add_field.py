import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
from database import db
from api_placeholders import terrasync_apis
from folium import plugins
import io
from PIL import Image
import numpy as np

# Placeholder function to get satellite image for given coordinates and zoom
def get_satellite_image(lat: float, lon: float, zoom: int = 18, width: int = 800, height: int = 600):
    """
    Placeholder: Fetch satellite image for the given location.
    In a real implementation, use a service like Google Static Maps, Mapbox, or tile compositing.
    For now, return a dummy image.
    """
    # Dummy image generation (replace with actual API call)
    img = Image.new('RGB', (width, height), color='lightblue')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    return img_byte_arr

# AI segmentation function using API - modified to return multiple fields
def run_ai_segmentation(image_data: bytes):
    """AI segmentation using TerraSync API - returns multiple detected fields"""
    result = terrasync_apis.detect_field_boundaries(image_data)
    if result["status"] == "success" and result["detected_fields"]:
        return result["detected_fields"]
    return []

def generate_crop_characteristics(crop_name: str):
    """Generate AI characteristics for crop"""
    return {
        "growth_rate": 0.5,
        "water_requirement": 100,
        "sun_requirement": 6,
        "crop_coefficient": 1.0,
        "irrigation_efficiency": 85
    }

def add_crop(crop_name: str, characteristics: dict, user_email: str):
    """Add crop to database"""
    crop_data = {
        "name": crop_name,
        **characteristics,
        "user_email": user_email
    }
    return db.add("crops", crop_data)

def calculate_polygon_area(polygon):
    """Calculate area of polygon in hectares (approximate)"""
    if len(polygon) < 3:
        return 0.0
    n = len(polygon)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += polygon[i][0] * polygon[j][1]
        area -= polygon[j][0] * polygon[i][1]
    area = abs(area) / 2.0
    # Rough conversion from degrees to m² (assumes small area)
    area_m2 = area * 111320**2 * np.cos(np.radians(polygon[0][0]))
    return area_m2 / 10000  # to hectares

def render_add_field():
    st.title("🌾 Add New Field")
    st.markdown("Tạo field mới: Nhập tọa độ, xem map vệ tinh, vẽ hoặc dùng AI để xác định polygon")
    
    # Get user email from Streamlit OAuth
    if not hasattr(st, 'user') or not st.user.is_logged_in:
        st.error("Vui lòng đăng nhập để thêm field")
        return
    
    user_email = st.user.email
    
    # Step 1: Enter coordinates and field name
    st.subheader("📍 Nhập Tọa Độ Vườn")
    col1, col2, col3 = st.columns([2, 2, 3])
    with col1:
        lat = st.number_input("Vĩ độ (Latitude)", value=20.450123, format="%.6f", key="lat_input")
    with col2:
        lon = st.number_input("Kinh độ (Longitude)", value=106.325678, format="%.6f", key="lon_input")
    with col3:
        field_name = st.text_input("Tên Field", placeholder="Nhập tên field", key="field_name")
    
    if lat and lon:
        # Step 2: Satellite Map View
        st.subheader("🗺️ Map Vệ Tinh")
        st.markdown("Map zoom đến tọa độ của bạn với ảnh vệ tinh thực tế")
        
        # Create map with satellite tiles (Esri World Imagery)
        m = folium.Map(location=[lat, lon], zoom_start=18, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri World Imagery')
        folium.Marker([lat, lon], popup="Tâm Vườn", icon=folium.Icon(color='red', icon='map-marker')).add_to(m)
        
        # Display initial map
        map_data = st_folium(m, width=700, height=400, key="initial_map")
        
        st.divider()
        
        # Step 3: Define Polygon - Draw or AI
        st.subheader("🎯 Xác Định Ranh Giới Field (Polygon)")
        col_draw, col_ai = st.columns(2)
        
        # Option 1: Draw Polygon
        with col_draw:
            st.markdown("**🖍️ Vẽ Polygon Thủ Công**")
            if st.button("Bắt Đầu Vẽ Trên Map", key="start_draw"):
                st.session_state.draw_mode = True
                st.rerun()
            
            if st.session_state.get('draw_mode', False):
                draw_m = folium.Map(location=[lat, lon], zoom_start=18, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
                folium.Marker([lat, lon], popup="Tâm Vườn").add_to(draw_m)
                
                # Add Draw control for polygon
                draw = plugins.Draw(
                    draw_options={'polyline': False, 'polygon': True, 'rectangle': False, 'circle': False, 'marker': False, 'circlemarker': False},
                    edit_options={'edit': False, 'remove': True}
                )
                draw_m.add_child(draw)
                
                drawn_data = st_folium(draw_m, width=700, height=400, key="draw_map", returned_objects=["last_active_drawing"])
                
                if drawn_data and 'last_active_drawing' in drawn_data and drawn_data['last_active_drawing']:
                    if drawn_data['last_active_drawing']['geometry']['type'] == 'Polygon':
                        polygon_coords = drawn_data['last_active_drawing']['geometry']['coordinates'][0]
                        st.session_state.polygon = [[coord[1], coord[0]] for coord in polygon_coords]  # Convert [lon, lat] to [lat, lon]
                        st.session_state.source = "manual"
                        st.success("✅ Đã vẽ polygon!")
                        if st.button("Xong Vẽ"):
                            st.session_state.draw_mode = False
                st.rerun()
            else:
                st.warning("👆 Vẽ polygon trên map (chỉ polygon)")
        
        # Option 2: AI Detection
        with col_ai:
            st.markdown("**🤖 Sử Dụng AI Phát Hiện**")
            if st.button("🔍 Chạy AI Trên Khu Vực Này", type="primary", key="run_ai"):
                with st.spinner("Đang chụp ảnh vệ tinh và phân tích AI..."):
                    # Get satellite image
                    image_data = get_satellite_image(lat, lon, zoom=18)
                    
                    # Display captured image
                    img = Image.open(io.BytesIO(image_data))
                    st.image(img, caption="Ảnh Vệ Tinh Được Chụp", use_container_width=True)
                    
                    # Run AI - get multiple fields
                    detected_fields = run_ai_segmentation(image_data)
                    
                    if detected_fields:
                        st.session_state.detected_fields = detected_fields
                        st.session_state.source = "ai"
                        st.success(f"✅ AI phát hiện {len(detected_fields)} field!")
                        st.rerun()
                    else:
                        st.error("❌ AI không phát hiện được. Thử điều chỉnh tọa độ.")
        
        # Display AI detected fields if available
        if st.session_state.get('source') == "ai" and 'detected_fields' in st.session_state:
            st.markdown("**🎯 Các Field AI Phát Hiện**")
            selected_field_idx = st.selectbox(
                "Chọn 1 field để sử dụng:",
                options=range(len(st.session_state.detected_fields)),
                format_func=lambda i: f"Field {i+1}: {st.session_state.detected_fields[i].get('crop_type_suggestion', 'Unknown')} (Diện tích: {st.session_state.detected_fields[i]['area_hectares']:.2f} ha, Độ tin cậy: {st.session_state.detected_fields[i]['confidence']*100:.1f}%)"
            )
            selected_polygon = st.session_state.detected_fields[selected_field_idx]['polygon']
            st.session_state.polygon = selected_polygon
            st.session_state.ai_confidence = st.session_state.detected_fields[selected_field_idx]['confidence']
            
            # Show selected on mini map
            ai_m = folium.Map(location=[lat, lon], zoom_start=18, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
            folium.Polygon(locations=selected_polygon, color='green', fill=True, fill_opacity=0.3).add_to(ai_m)
            st_folium(ai_m, width=400, height=250)
            
            if st.button("Sử Dụng Field Này"):
                st.success("✅ Đã chọn polygon từ AI!")
        
        # Step 4: Field Details if polygon available
        if st.session_state.get('polygon'):
            st.divider()
            st.subheader("📝 Thông Tin Field")
            
            area = calculate_polygon_area(st.session_state.polygon)
            st.metric("Diện Tích Tự Động Tính", f"{area:.2f} ha")
            
            with st.form("field_details"):
                col1, col2 = st.columns(2)
                
                with col1:
                    # Field name already input above, but confirm
                    st.text_input("Tên Field", value=field_name, key="confirm_name", disabled=True)
                    crop = st.selectbox("Loại Cây Trồng", 
                        ["Rice", "Corn", "Wheat", "Soybean", "Tomato", "Potato", "Cabbage", "Other"]
                    )
                    stage = st.selectbox("Giai Đoạn Sinh Trưởng", 
                        ["Seedling", "Vegetative", "Flowering", "Fruiting", "Maturity"]
                    )
                
                with col2:
                    if crop == "Other":
                        custom_crop = st.text_input("Nhập Tên Cây Trồng Khác", placeholder="Ví dụ: Durian")
                        if custom_crop:
                            # AI predict characteristics for custom crop
                            with st.spinner("AI đang dự đoán đặc tính cho cây trồng..."):
                                characteristics = generate_crop_characteristics(custom_crop)  # Assume API call
                            crop_coeff = st.number_input("Hệ Số Cây Trồng (AI Dự Đoán)", value=characteristics["crop_coefficient"], step=0.1)
                            irr_eff = st.number_input("Hiệu Suất Tưới Tiết (%) (AI Dự Đoán)", value=characteristics["irrigation_efficiency"], min_value=50, max_value=100)
                        else:
                            st.warning("Vui lòng nhập tên cây trồng để AI dự đoán")
                            crop_coeff = 1.0
                            irr_eff = 85
                    else:
                        characteristics = generate_crop_characteristics(crop)
                        crop_coeff = st.number_input("Hệ Số Cây Trồng", value=characteristics["crop_coefficient"], step=0.1)
                        irr_eff = st.number_input("Hiệu Suất Tưới Tiết (%)", value=characteristics["irrigation_efficiency"], min_value=50, max_value=100)
                
                submitted = st.form_submit_button("✅ Thêm Field Vào Farm", type="primary")
                
                if submitted:
                    if not field_name:
                        st.error("Vui lòng nhập tên field")
                    else:
                        # Add crop if needed
                        actual_crop = custom_crop if crop == "Other" and custom_crop else crop
                        add_crop(actual_crop, generate_crop_characteristics(actual_crop), user_email)
                        
                        center_lat = sum(p[0] for p in st.session_state.polygon) / len(st.session_state.polygon)
                        center_lon = sum(p[1] for p in st.session_state.polygon) / len(st.session_state.polygon)
                        
                        field_data = {
                            'name': field_name,
                            'crop': actual_crop,
                            'area': area,
                            'polygon': st.session_state.polygon,
                            'center': [center_lat, center_lon],
                            'lat': lat,
                            'lon': lon,
                            'stage': stage,
                            'crop_coefficient': crop_coeff,
                            'irrigation_efficiency': irr_eff,
                            'status': 'hydrated',
                            'today_water': 100,
                            'time_needed': 2,
                            'progress': 50,
                            'days_to_harvest': 60
                        }
                        
                        if st.session_state.get('source') == "ai":
                            field_data['detection_confidence'] = st.session_state.ai_confidence
                        
                        # Add field to database
                        success = db.add_user_field(user_email, field_data)
                        
                        if success:
                            st.success("✅ Field đã được thêm thành công!")
                            
                            # Clear session state
                            for key in ['polygon', 'source', 'draw_mode', 'detected_fields', 'ai_confidence']:
                                if key in st.session_state:
                                    del st.session_state[key]
                            
                            # Show success message and redirect option
                            st.balloons()
                            
                            col1, col2, col3 = st.columns([1, 2, 1])
                            with col2:
                                if st.button("🌾 Xem Fields của tôi", type="primary", use_container_width=True):
                                    # Set session state to navigate to My Fields
                                    st.session_state.navigate_to = "My Fields"
                            
                            # Auto redirect after 3 seconds
                            import time
                            with st.spinner("Đang chuyển hướng đến trang My Fields..."):
                                time.sleep(2)
                                st.session_state.navigate_to = "My Fields"
                                st.rerun()
                        else:
                            st.error("❌ Lỗi khi thêm field vào database")
        else:
            st.info("👆 Vẽ polygon thủ công hoặc chạy AI để tiếp tục")
    else:
        st.warning("Vui lòng nhập tọa độ để bắt đầu")