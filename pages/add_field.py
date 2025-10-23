import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
from io import BytesIO
from PIL import Image
import numpy as np
from database import db
from api_placeholders import terrasync_apis

# AI segmentation function using API with tile image
def run_ai_segmentation(image_data: bytes, lat: float, lon: float):
    """AI segmentation using TerraSync API with tile image at given coordinates"""
    result = terrasync_apis.detect_field_boundaries(image_data, lat=lat, lon=lon)
    if result["status"] == "success" and result["detected_fields"]:
        return result["detected_fields"][0]["polygon"]
    return None

def generate_crop_characteristics(crop_name: str):
    """Generate AI characteristics for crop"""
    return {
        "growth_rate": 0.5,
        "water_requirement": 100,
        "sun_requirement": 6,
        "crop_coefficient": 1.0,
        "irrigation_efficiency": 85
    }

def add_crop(crop_name: str, characteristics: dict):
    """Add crop to database"""
    crop_data = {
        "name": crop_name,
        **characteristics,
        "user_email": st.user.email
    }
    return db.add("crops", crop_data)

def get_satellite_tile_image(lat: float, lon: float, zoom: int = 16, size: int = 512):
    """Fetch satellite tile image for given coordinates using a mapping service"""
    # Using OpenStreetMap Mapnik tiles for satellite-like imagery (replace with actual satellite API if available)
    tile_url = f"https://tile.openstreetmap.org/{zoom}/{int(lon_to_tile(lon, zoom))}/{int(lat_to_tile(lat, zoom))}.png"
    response = requests.get(tile_url)
    if response.status_code == 200:
        return BytesIO(response.content)
    return None

def lat_to_tile(lat: float, zoom: int):
    """Convert latitude to tile Y coordinate"""
    lat_rad = np.radians(lat)
    n = 2.0 ** zoom
    return (1.0 - np.log(np.tan(lat_rad) + (1 / np.cos(lat_rad))) / np.pi) / 2.0 * n

def lon_to_tile(lon: float, zoom: int):
    """Convert longitude to tile X coordinate"""
    n = 2.0 ** zoom
    return ((lon + 180.0) / 360.0) * n

def render_add_field():
    st.title("🌾 Add New Field")
    st.markdown("Create a new field using AI detection, manual coordinates, or map drawing")

    # Location input for all methods
    st.subheader("📍 Field Location")
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("Latitude", value=20.450123, format="%.6f")
    with col2:
        lon = st.number_input("Longitude", value=106.325678, format="%.6f")

    # Create map with satellite tiles
    m = folium.Map(
        location=[lat, lon],
        zoom_start=16,
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri World Imagery'
    )

    # Method selection
    method = st.radio(
        "Choose Field Creation Method:",
        ["🤖 AI Field Detection (Satellite Image)", "📍 Manual Coordinates", "🗺️ Map Drawing"],
        horizontal=True
    )

    st.divider()

    # Display map
    map_data = st_folium(m, width=700, height=400, returned_objects=["last_object_clicked"])

    if method == "🤖 AI Field Detection (Satellite Image)":
        render_ai_field_detection(lat, lon, m)
    elif method == "📍 Manual Coordinates":
        render_manual_coordinates(lat, lon, m)
    else:
        render_map_drawing(lat, lon, map_data, m)

def render_ai_field_detection(lat: float, lon: float, map_obj):
    """AI Field Detection using satellite tile image"""
    st.subheader("🤖 AI Field Detection")
    st.markdown("Analyze satellite imagery at the specified coordinates to detect field boundaries")

    if st.button("🔍 Detect Field Boundaries", type="primary"):
        with st.spinner("Fetching and analyzing satellite image..."):
            # Fetch satellite tile image
            tile_image = get_satellite_tile_image(lat, lon)
            if tile_image:
                # Display tile image
                st.image(tile_image, caption="Satellite Image", use_container_width=True)
                
                # Process with AI
                image_data = tile_image.getvalue()
                polygon = run_ai_segmentation(image_data, lat, lon)
                
                if polygon:
                    st.session_state.detected_fields = [{
                        "polygon": polygon,
                        "confidence": 0.95,  # Mock confidence
                        "area_hectares": 1.0,  # Mock area
                        "crop_type_suggestion": "Rice"  # Mock crop suggestion
                    }]
                    st.success("✅ Field boundaries detected!")
                    st.rerun()
                else:
                    st.error("❌ Failed to detect field boundaries. Try adjusting coordinates.")
            else:
                st.error("❌ Failed to fetch satellite image.")

    # Display detected fields
    if "detected_fields" in st.session_state:
        st.subheader("🎯 Detected Fields")
        
        for i, field in enumerate(st.session_state.detected_fields):
            with st.expander(f"Field {i+1}: {field.get('crop_type_suggestion', 'Unknown Crop')}", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Confidence", f"{field['confidence']*100:.1f}%")
                    st.metric("Area", f"{field['area_hectares']:.2f} hectares")
                    st.metric("Crop Type", field.get('crop_type_suggestion', 'Unknown'))
                
                with col2:
                    # Show polygon on map
                    if field.get('polygon'):
                        folium.Polygon(
                            locations=field['polygon'],
                            color='green',
                            fill=True,
                            fill_opacity=0.3
                        ).add_to(map_obj)
                        st_folium(map_obj, width=400, height=300)
                
                # Field details form
                with st.form(f"field_details_{i}"):
                    st.write("**Field Details:**")
                    name = st.text_input("Field Name", value=f"AI Field {i+1}")
                    crop = st.selectbox("Crop Type", 
                        ["Rice", "Corn", "Wheat", "Soybean", "Tomato", "Potato", "Cabbage", "Other"],
                        index=0 if field.get('crop_type_suggestion') == 'Rice' else 1
                    )
                    stage = st.selectbox("Growth Stage", 
                        ["Seedling", "Vegetative", "Flowering", "Fruiting", "Maturity"]
                    )
                    
                    if st.form_submit_button("✅ Add This Field", type="primary"):
                        # Save to database
                        field_data = {
                            'name': name,
                            'crop': crop,
                            'area': field['area_hectares'],
                            'polygon': field['polygon'],
                            'center': [
                                sum(p[0] for p in field['polygon']) / len(field['polygon']),
                                sum(p[1] for p in field['polygon']) / len(field['polygon'])
                            ],
                            'lat': lat,
                            'lon': lon,
                            'stage': stage,
                            'detection_confidence': field['confidence'],
                            'status': 'hydrated',
                            'today_water': 100,
                            'time_needed': 2,
                            'progress': 50,
                            'days_to_harvest': 60
                        }
                        
                        if db.add_user_field(st.user.email, field_data):
                            st.success("✅ Field added successfully!")
                            st.session_state.detected_fields.pop(i)
                            if not st.session_state.detected_fields:
                                del st.session_state.detected_fields
                            st.rerun()
                        else:
                            st.error("❌ Failed to add field")

def render_manual_coordinates(lat: float, lon: float, map_obj):
    """Manual field creation with coordinates"""
    st.subheader("📍 Manual Field Creation")
    st.markdown("Enter field details manually")
    
    with st.form("manual_field"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Field Name", placeholder="Enter field name")
            crop = st.selectbox("Crop Type", 
                ["Rice", "Corn", "Wheat", "Soybean", "Tomato", "Potato", "Cabbage", "Other"]
            )
            area = st.number_input("Area (hectares)", min_value=0.1, value=1.0, step=0.1)
            stage = st.selectbox("Growth Stage", 
                ["Seedling", "Vegetative", "Flowering", "Fruiting", "Maturity"]
            )
        
        with col2:
            crop_coefficient = st.number_input("Crop Coefficient", min_value=0.1, max_value=2.0, value=1.0, step=0.1)
            irrigation_efficiency = st.number_input("Irrigation Efficiency (%)", min_value=50, max_value=100, value=85)
        
        # Show map preview with marker
        folium.Marker([lat, lon], popup="Field Center").add_to(map_obj)
        st_folium(map_obj, width=700, height=400)
        
        if st.form_submit_button("✅ Add Field", type="primary"):
            if not name:
                st.error("Please enter a field name")
            else:
                # Create simple polygon
                polygon = [
                    [lat - 0.0005, lon - 0.0005],
                    [lat + 0.0005, lon - 0.0005],
                    [lat + 0.0005, lon + 0.0005],
                    [lat - 0.0005, lon + 0.0005]
                ]
                
                field_data = {
                    'name': name,
                    'crop': crop,
                    'area': area,
                    'lat': lat,
                    'lon': lon,
                    'center': [lat, lon],
                    'polygon': polygon,
                    'stage': stage,
                    'crop_coefficient': crop_coefficient,
                    'irrigation_efficiency': irrigation_efficiency,
                    'status': 'hydrated',
                    'today_water': 100,
                    'time_needed': 2,
                    'progress': 50,
                    'days_to_harvest': 60
                }
                
                if db.add_user_field(st.user.email, field_data):
                    st.success("✅ Field added successfully!")
                    st.rerun()
                else:
                    st.error("❌ Failed to add field")

def render_map_drawing(lat: float, lon: float, map_data, map_obj):
    """Map drawing interface"""
    st.subheader("🗺️ Map Drawing")
    st.markdown("Draw your field boundaries on the satellite map")
    
    # Get clicked location or use provided coordinates
    clicked_lat = map_data["last_object_clicked"]["lat"] if map_data.get("last_object_clicked") else lat
    clicked_lon = map_data["last_object_clicked"]["lng"] if map_data.get("last_object_clicked") else lon
    
    if map_data.get("last_object_clicked"):
        st.success(f"📍 Selected location: {clicked_lat:.6f}, {clicked_lon:.6f}")
        folium.Marker([clicked_lat, clicked_lon], popup="Selected Point").add_to(map_obj)
        st_folium(map_obj, width=700, height=400)
    
    # Field details form
    with st.form("map_field"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Field Name", placeholder="Enter field name")
            crop = st.selectbox("Crop Type", 
                ["Rice", "Corn", "Wheat", "Soybean", "Tomato", "Potato", "Cabbage", "Other"]
            )
            area = st.number_input("Area (hectares)", min_value=0.1, value=1.0, step=0.1)
        
        with col2:
            stage = st.selectbox("Growth Stage", 
                ["Seedling", "Vegetative", "Flowering", "Fruiting", "Maturity"]
            )
            crop_coefficient = st.number_input("Crop Coefficient", min_value=0.1, max_value=2.0, value=1.0, step=0.1)
            irrigation_efficiency = st.number_input("Irrigation Efficiency (%)", min_value=50, max_value=100, value=85)
        
        if st.form_submit_button("✅ Add Field", type="primary"):
            if not name:
                st.error("Please enter a field name")
            else:
                # Create polygon around clicked point
                polygon = [
                    [clicked_lat - 0.0005, clicked_lon - 0.0005],
                    [clicked_lat + 0.0005, clicked_lon - 0.0005],
                    [clicked_lat + 0.0005, clicked_lon + 0.0005],
                    [clicked_lat - 0.0005, clicked_lon + 0.0005]
                ]
                
                field_data = {
                    'name': name,
                    'crop': crop,
                    'area': area,
                    'lat': clicked_lat,
                    'lon': clicked_lon,
                    'center': [clicked_lat, clicked_lon],
                    'polygon': polygon,
                    'stage': stage,
                    'crop_coefficient': crop_coefficient,
                    'irrigation_efficiency': irrigation_efficiency,
                    'status': 'hydrated',
                    'today_water': 100,
                    'time_needed': 2,
                    'progress': 50,
                    'days_to_harvest': 60
                }
                
                if db.add_user_field(st.user.email, field_data):
                    st.success("✅ Field added successfully!")
                    st.rerun()
                else:
                    st.error("❌ Failed to add field")
    
    if not map_data.get("last_object_clicked"):
        st.info("👆 Click on the map to select field location")