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
from datetime import datetime

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

# Dictionary với tham số hạt giống có sẵn
CROP_DATABASE = {
    "Rice": {
        "growth_rate": 0.8,
        "water_requirement": 120,
        "sun_requirement": 8,
        "crop_coefficient": 1.1,
        "irrigation_efficiency": 80,
        "planting_season": "Wet season",
        "harvest_days": 120,
        "soil_type": "Clay loam",
        "ph_range": "6.0-7.0"
    },
    "Corn": {
        "growth_rate": 0.9,
        "water_requirement": 100,
        "sun_requirement": 10,
        "crop_coefficient": 1.0,
        "irrigation_efficiency": 85,
        "planting_season": "Dry season",
        "harvest_days": 90,
        "soil_type": "Sandy loam",
        "ph_range": "6.0-7.5"
    },
    "Wheat": {
        "growth_rate": 0.7,
        "water_requirement": 80,
        "sun_requirement": 8,
        "crop_coefficient": 0.9,
        "irrigation_efficiency": 90,
        "planting_season": "Cool season",
        "harvest_days": 150,
        "soil_type": "Loam",
        "ph_range": "6.0-7.5"
    },
    "Soybean": {
        "growth_rate": 0.6,
        "water_requirement": 90,
        "sun_requirement": 8,
        "crop_coefficient": 0.8,
        "irrigation_efficiency": 85,
        "planting_season": "Warm season",
        "harvest_days": 100,
        "soil_type": "Well-drained loam",
        "ph_range": "6.0-7.0"
    },
    "Tomato": {
        "growth_rate": 1.0,
        "water_requirement": 110,
        "sun_requirement": 10,
        "crop_coefficient": 1.2,
        "irrigation_efficiency": 75,
        "planting_season": "Warm season",
        "harvest_days": 75,
        "soil_type": "Sandy loam",
        "ph_range": "6.0-6.8"
    },
    "Potato": {
        "growth_rate": 0.8,
        "water_requirement": 95,
        "sun_requirement": 8,
        "crop_coefficient": 1.0,
        "irrigation_efficiency": 80,
        "planting_season": "Cool season",
        "harvest_days": 90,
        "soil_type": "Sandy loam",
        "ph_range": "5.0-6.5"
    },
    "Cabbage": {
        "growth_rate": 0.7,
        "water_requirement": 85,
        "sun_requirement": 6,
        "crop_coefficient": 0.9,
        "irrigation_efficiency": 85,
        "planting_season": "Cool season",
        "harvest_days": 70,
        "soil_type": "Loam",
        "ph_range": "6.0-7.0"
    }
}

def get_crop_characteristics(crop_name: str):
    """Lấy tham số hạt giống từ database hoặc tạo mới"""
    # Kiểm tra trong database có sẵn
    if crop_name in CROP_DATABASE:
        return CROP_DATABASE[crop_name]
    
    # Nếu không có, tạo tham số mặc định (AI-generated defaults)
    return {
        "growth_rate": 0.7,
        "water_requirement": 100,
        "sun_requirement": 8,
        "crop_coefficient": 1.0,
        "irrigation_efficiency": 85,
        "planting_season": "General",
        "harvest_days": 90,
        "soil_type": "Loam",
        "ph_range": "6.0-7.0"
    }

def add_crop_if_not_exists(crop_name: str, user_email: str):
    """Thêm crop vào database nếu chưa tồn tại"""
    # Kiểm tra crop đã tồn tại chưa
    existing_crops = db.get("crops", {"name": crop_name, "user_email": user_email})
    if existing_crops:
        return True  # Crop đã tồn tại
    
    # Lấy tham số cho crop
    characteristics = get_crop_characteristics(crop_name)
    
    # Thêm crop mới
    crop_data = {
        "name": crop_name,
        **characteristics,
        "user_email": user_email,
        "created_at": datetime.now().isoformat(),
        "is_ai_generated": crop_name not in CROP_DATABASE
    }
    return db.add("crops", crop_data)

@st.cache_data
def get_available_crops(user_email: str):
    """Lấy danh sách crops có sẵn cho user"""
    # Lấy crops từ database của user
    user_crops = db.get("crops", {"user_email": user_email})
    user_crop_names = [crop["name"] for crop in user_crops]
    
    # Kết hợp với crops có sẵn trong CROP_DATABASE
    all_crops = list(CROP_DATABASE.keys())
    
    # Thêm crops từ database của user (tránh trùng lặp)
    for crop_name in user_crop_names:
        if crop_name not in all_crops:
            all_crops.append(crop_name)
    
    return sorted(all_crops)

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
    
    # Initialize session state if needed
    if 'draw_mode' not in st.session_state:
        st.session_state.draw_mode = False
    if 'source' not in st.session_state:
        st.session_state.source = None
    if 'form_submitted' not in st.session_state:
        st.session_state.form_submitted = False
    
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
                st.session_state.source = "manual"
                st.rerun()
            
            if st.session_state.draw_mode:
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
                        st.success("✅ Đã vẽ polygon!")
                
                if st.button("Xong Vẽ", key="done_draw"):
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
        if st.session_state.source == "ai" and 'detected_fields' in st.session_state:
            st.markdown("**🎯 Các Field AI Phát Hiện**")
            selected_field_idx = st.selectbox(
                "Chọn 1 field để sử dụng:",
                options=range(len(st.session_state.detected_fields)),
                format_func=lambda i: f"Field {i+1}: {st.session_state.detected_fields[i].get('crop_type_suggestion', 'Unknown')} (Diện tích: {st.session_state.detected_fields[i].get('area_hectares', 0):.2f} ha, Độ tin cậy: {st.session_state.detected_fields[i].get('confidence', 0)*100:.1f}%)",
                key="ai_select"
            )
            selected_polygon = st.session_state.detected_fields[selected_field_idx]['polygon']
            st.session_state.polygon = selected_polygon
            st.session_state.ai_confidence = st.session_state.detected_fields[selected_field_idx]['confidence']
            
            # Show selected on mini map
            ai_m = folium.Map(location=[lat, lon], zoom_start=18, tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
            folium.Polygon(locations=selected_polygon, color='green', fill=True, fill_opacity=0.3).add_to(ai_m)
            st_folium(ai_m, width=400, height=250, key="ai_mini_map")
            
            if st.button("Sử Dụng Field Này", key="use_ai_field"):
                st.success("✅ Đã chọn polygon từ AI!")
                st.rerun()
        
        # Step 4: Field Details if polygon available
        if 'polygon' in st.session_state:
            st.divider()
            st.subheader("📝 Thông Tin Field")
            
            area = calculate_polygon_area(st.session_state.polygon)
            st.metric("Diện Tích Tự Động Tính", f"{area:.2f} ha")
            
            # Form for field details
            with st.form("field_details"):
                col1, col2 = st.columns(2)
                
                with col1:
                    # Field name already input above, but confirm
                    st.text_input("Tên Field", value=field_name, key="confirm_name", disabled=True)
                    
                    # Lấy danh sách crops có sẵn cho user (cached)
                    available_crops = get_available_crops(user_email)
                    crop_options = available_crops + ["Other"]
                    
                    crop = st.selectbox("Loại Cây Trồng", crop_options, key="crop_select")
                    stage = st.selectbox("Giai Đoạn Sinh Trưởng", 
                        ["Seedling", "Vegetative", "Flowering", "Fruiting", "Maturity"], key="stage_select"
                    )
                
                with col2:
                    if crop == "Other":
                        custom_crop = st.text_input("Nhập Tên Cây Trồng Khác", placeholder="Ví dụ: Durian, Mango, Coffee...", key="custom_crop")
                        if custom_crop:
                            # Lấy tham số cho crop mới (AI-generated defaults)
                            characteristics = get_crop_characteristics(custom_crop)
                            
                            st.info(f"🤖 AI đã tạo tham số mặc định cho **{custom_crop}**")
                            
                            # Hiển thị thông tin crop mới
                            col_info1, col_info2 = st.columns(2)
                            with col_info1:
                                st.metric("Mùa Trồng", characteristics["planting_season"])
                                st.metric("Ngày Thu Hoạch", f"{characteristics['harvest_days']} ngày")
                            with col_info2:
                                st.metric("Loại Đất", characteristics["soil_type"])
                                st.metric("pH", characteristics["ph_range"])
                            
                            crop_coeff = st.number_input("Hệ Số Cây Trồng (AI Dự Đoán)", 
                                                       value=characteristics["crop_coefficient"], 
                                                       step=0.1, min_value=0.1, max_value=2.0, key="coeff_other")
                            irr_eff = st.number_input("Hiệu Suất Tưới Tiết (%) (AI Dự Đoán)", 
                                                    value=characteristics["irrigation_efficiency"], 
                                                    min_value=50, max_value=100, key="eff_other")
                        else:
                            st.warning("Vui lòng nhập tên cây trồng để AI tạo tham số")
                            crop_coeff = st.number_input("Hệ Số Cây Trồng", value=1.0, step=0.1, min_value=0.1, max_value=2.0, key="coeff_other_default")
                            irr_eff = st.number_input("Hiệu Suất Tưới Tiết (%)", value=85, min_value=50, max_value=100, key="eff_other_default")
                    else:
                        # Lấy tham số cho crop đã có
                        characteristics = get_crop_characteristics(crop)
                        
                        # Hiển thị thông tin crop
                        st.info(f"📊 Thông tin **{crop}**:")
                        col_info1, col_info2 = st.columns(2)
                        with col_info1:
                            st.metric("Mùa Trồng", characteristics["planting_season"])
                            st.metric("Ngày Thu Hoạch", f"{characteristics['harvest_days']} ngày")
                        with col_info2:
                            st.metric("Loại Đất", characteristics["soil_type"])
                            st.metric("pH", characteristics["ph_range"])
                        
                        crop_coeff = st.number_input("Hệ Số Cây Trồng", 
                                                   value=characteristics["crop_coefficient"], 
                                                   step=0.1, min_value=0.1, max_value=2.0, key="coeff_standard")
                        irr_eff = st.number_input("Hiệu Suất Tưới Tiết (%)", 
                                                value=characteristics["irrigation_efficiency"], 
                                                min_value=50, max_value=100, key="eff_standard")
                
                submitted = st.form_submit_button("✅ Thêm Field Vào Farm", type="primary")
            
            # Handle form submission outside the form
            if submitted:
                if not field_name:
                    st.error("Vui lòng nhập tên field")
                    st.rerun()
                
                # Xác định crop thực tế
                if crop == "Other":
                    if not st.session_state.get("custom_crop", "").strip():
                        st.error("Vui lòng nhập tên cây trồng khác")
                        st.rerun()
                    actual_crop = st.session_state.get("custom_crop", "").strip()
                else:
                    actual_crop = crop
                
                # Thêm crop vào database nếu chưa tồn tại (tránh trùng tên per user)
                crop_added = add_crop_if_not_exists(actual_crop, user_email)
                
                if crop_added:
                    st.success(f"✅ Crop '{actual_crop}' đã được thêm vào database")
                else:
                    st.info(f"ℹ️ Crop '{actual_crop}' đã có trong database")
                
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
                
                if st.session_state.source == "ai":
                    field_data['detection_confidence'] = st.session_state.ai_confidence
                
                # Add field to database
                success = db.add_user_field(user_email, field_data)
                
                if success:
                    st.success("✅ Field đã được thêm thành công!")
                    st.session_state.form_submitted = True
                    st.balloons()
                    
                    # Clear session state for polygon etc.
                    for key in ['polygon', 'source', 'draw_mode', 'detected_fields', 'ai_confidence']:
                        if key in st.session_state:
                            del st.session_state[key]
                    
                    st.rerun()
                else:
                    st.error("❌ Lỗi khi thêm field vào database")
                    st.rerun()
        
        # Success message and navigation button (outside any form)
        if st.session_state.get('form_submitted', False):
            st.divider()
            st.success("🎉 Field đã được thêm thành công! Chuyển hướng đến trang My Fields.")
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("🌾 Xem Fields của tôi", type="primary", use_container_width=True, key="navigate_button"):
                    st.session_state.navigate_to = "My Fields"
                    st.session_state.form_submitted = False
                    st.rerun()
            
            # Auto navigate after a delay if not clicked
            # Note: Streamlit doesn't support sleep without blocking, so use a placeholder
            st.info("Tự động chuyển hướng sau 3 giây...")
        
        else:
            if 'polygon' not in st.session_state:
                st.info("👆 Vẽ polygon thủ công hoặc chạy AI để tiếp tục")
    else:
        st.warning("Vui lòng nhập tọa độ để bắt đầu")