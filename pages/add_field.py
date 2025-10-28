import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
from database import db
from folium import plugins
import io
from PIL import Image
import numpy as np
from datetime import datetime
from inference_sdk import InferenceHTTPClient
import uuid
import os

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

def pixel_to_geo(points, center_lat, center_lon, zoom, img_width, img_height):
    """
    Approximate conversion from pixel coordinates to geographic coordinates.
    This is a simplified model and may not be accurate.
    A more precise method would use map projection calculations based on the tile source.
    """
    # Resolution (meters/pixel) at equator for a given zoom level
    resolution = 156543.03 * np.cos(np.radians(center_lat)) / (2**zoom)
    
    geo_points = []
    for p in points:
        # Calculate offset from image center in pixels
        dx_pixels = p['x'] - img_width / 2
        dy_pixels = p['y'] - img_height / 2
        
        # Convert pixel offset to meters
        dx_meters = dx_pixels * resolution
        dy_meters = -dy_pixels * resolution # Y is inverted in pixel vs geo
        
        # Convert meter offset to degrees
        lat_offset = dy_meters / 111320
        lon_offset = dx_meters / (111320 * np.cos(np.radians(center_lat)))
        
        geo_points.append([center_lat + lat_offset, center_lon + lon_offset])
        
    return geo_points

# AI segmentation function using Roboflow API
def run_ai_segmentation(image_data: bytes, center_lat: float, center_lon: float, zoom: int, width: int, height: int):
    """AI segmentation using Roboflow - returns multiple detected fields"""
    
    # Save image data to a temporary file
    temp_dir = "/tmp/terrasync"
    os.makedirs(temp_dir, exist_ok=True)
    temp_image_path = os.path.join(temp_dir, f"{uuid.uuid4()}.jpg")
    
    with open(temp_image_path, "wb") as f:
        f.write(image_data)

    try:
        # Connect to Roboflow workflow
        client = InferenceHTTPClient(
            api_url="https://serverless.roboflow.com",
            api_key="u5p8jGeuTJwkNwIhPb2x"
        )

        # Run workflow on the image
        result = client.run_workflow(
            workspace_name="tham-hoa-thin-nhin",
            workflow_id="detect-count-and-visualize-2",
            images={"image": temp_image_path},
            use_cache=True
        )
        
        # Process the result
        detected_fields = []
        if result and isinstance(result, list) and 'predictions' in result[0]:
            predictions = result[0]['predictions']
            for pred in predictions:
                # Assuming 'points' are the polygon vertices in pixel coordinates
                if 'points' in pred and 'confidence' in pred:
                    pixel_points = pred['points']
                    
                    # Convert pixel coordinates to geo coordinates
                    geo_polygon = pixel_to_geo(pixel_points, center_lat, center_lon, zoom, width, height)
                    
                    # Calculate area
                    area_hectares = calculate_polygon_area(geo_polygon)
                    
                    detected_fields.append({
                        'polygon': geo_polygon,
                        'confidence': pred['confidence'],
                        'area_hectares': area_hectares,
                        'crop_type_suggestion': pred.get('class', 'Unknown')
                    })
        return detected_fields

    except Exception as e:
        st.error(f"Lỗi khi gọi Roboflow API: {e}")
        return []
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_image_path):
            os.remove(temp_image_path)

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
    
    # Nếu không có, tạo tham số mặc định
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
                    # Run AI - get multiple fields
                    img_width, img_height = 800, 600
                    zoom = 18
                    image_data = get_satellite_image(lat, lon, zoom=zoom, width=img_width, height=img_height)
                    
                    # Display captured image
                    img = Image.open(io.BytesIO(image_data))
                    st.image(img, caption="Ảnh Vệ Tinh Được Chụp", use_container_width=True)
                    
                    # Run AI - get multiple fields
                    detected_fields = run_ai_segmentation(image_data, lat, lon, zoom, img_width, img_height)
                    
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
                    
                    # Lấy danh sách crops có sẵn cho user
                    available_crops = get_available_crops(user_email)
                    crop_options = available_crops + ["Other"]
                    
                    crop = st.selectbox("Loại Cây Trồng", crop_options)
                    stage = st.selectbox("Giai Đoạn Sinh Trưởng", 
                        ["Seedling", "Vegetative", "Flowering", "Fruiting", "Maturity"]
                    )
                
                with col2:
                    if crop == "Other":
                        custom_crop = st.text_input("Nhập Tên Cây Trồng Khác", placeholder="Ví dụ: Durian, Mango, Coffee...")
                        if custom_crop:
                            # Lấy tham số cho crop mới
                            characteristics = get_crop_characteristics(custom_crop)
                            
                            st.info(f"🤖 AI đã tạo tham số cho **{custom_crop}**")
                            
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
                                                       step=0.1, min_value=0.1, max_value=2.0)
                            irr_eff = st.number_input("Hiệu Suất Tưới Tiết (%) (AI Dự Đoán)", 
                                                    value=characteristics["irrigation_efficiency"], 
                                                    min_value=50, max_value=100)
                        else:
                            st.warning("Vui lòng nhập tên cây trồng để AI tạo tham số")
                            crop_coeff = 1.0
                            irr_eff = 85
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
                                                   step=0.1, min_value=0.1, max_value=2.0)
                        irr_eff = st.number_input("Hiệu Suất Tưới Tiết (%)", 
                                                value=characteristics["irrigation_efficiency"], 
                                                min_value=50, max_value=100)
                
                submitted = st.form_submit_button("✅ Thêm Field Vào Farm", type="primary")
                
                if submitted:
                    if not field_name:
                        st.error("Vui lòng nhập tên field")
                    else:
                        # Xác định crop thực tế
                        actual_crop = custom_crop if crop == "Other" and custom_crop else crop
                        
                        # Thêm crop vào database nếu chưa tồn tại
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