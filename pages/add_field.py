import os
import io
import uuid
import time
import base64
import logging
import requests
from requests.adapters import HTTPAdapter, Retry
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any

import streamlit as st
import folium
from streamlit_folium import st_folium
from folium import plugins
from folium.features import GeoJson

from PIL import Image
import numpy as np
import toml
from pathlib import Path

# --- IMPORT CUSTOM MODULES ---
from database import db, crop_db 
from inference_sdk import InferenceHTTPClient
from utils import predict_water_needs

# --- CẤU HÌNH ---
@st.cache_resource
def load_config():
    config_path = Path(".streamlit/appcfg.toml")
    if not config_path.exists():
        return {}
    try:
        return toml.load(config_path)
    except Exception as e:
        st.error(f"Lỗi config: {e}")
        return {}

config = load_config()
api_cfg = config.get("api", {})
API_URL = api_cfg.get("aifield_url", "http://172.24.193.209:9990")
ROBOFLOW_API_KEY = st.secrets.get("roboflow", {}).get("api_key")
REQUEST_TIMEOUT = 120
MAX_IMAGE_BYTES = 200 * 1024 * 1024

_session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
_session.mount("https://", HTTPAdapter(max_retries=retries))
_session.mount("http://", HTTPAdapter(max_retries=retries))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("add_field_app")

# --- CÁC HÀM HỖ TRỢ (UTILITIES) ---

def safe_post_json(url: str, json_data: dict, timeout: int = REQUEST_TIMEOUT) -> requests.Response:
    return _session.post(url, json=json_data, timeout=timeout)

def calculate_polygon_area(polygon: List[List[float]]) -> float:
    if not polygon or len(polygon) < 3:
        return 0.0
    coords = [(p[1], p[0]) for p in polygon]
    n = len(coords)
    area = 0.0
    for i in range(n):
        x1, y1 = coords[i]
        x2, y2 = coords[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    area = abs(area) / 2.0
    avg_lat = np.mean([p[0] for p in polygon])
    avg_lat_rad = np.radians(avg_lat)
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * np.cos(avg_lat_rad)
    area_m2 = area * m_per_deg_lon * m_per_deg_lat
    return float(area_m2 / 10000.0) # Đổi sang Ha

def pixel_to_geo_bbox(points: List[dict], bbox_coords: List[List[float]], img_width: int, img_height: int) -> List[List[float]]:
    lats = [p[0] for p in bbox_coords]
    lons = [p[1] for p in bbox_coords]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    lat_range = max_lat - min_lat
    lon_range = max_lon - min_lon

    geo = []
    for pt in points:
        if isinstance(pt, dict):
            x = pt.get("x") or pt.get("X") or pt.get("col") or pt.get("cx")
            y = pt.get("y") or pt.get("Y") or pt.get("row") or pt.get("cy")
        else:
            x, y = pt[0], pt[1]
        x, y = float(x), float(y)
        x_norm = x / float(max(1, img_width))
        y_norm = y / float(max(1, img_height))
        lat = max_lat - y_norm * lat_range
        lon = min_lon + x_norm * lon_range
        geo.append([float(lat), float(lon)])
    return geo

def get_satellite_image_bbox(bbox_coords_ui: List[List[float]], cloud: float = 70.0, days: int = 100, upscale: int = 1) -> Optional[bytes]:
    send_coords = [[float(p[1]), float(p[0])] for p in bbox_coords_ui]
    payload = {
        "coords": send_coords,
        "cloud": float(cloud),
        "days": int(days),
        "upscale": int(upscale)
    }
    url = f"{API_URL.rstrip('/')}/process_satellite_image"
    try:
        resp = safe_post_json(url, json_data=payload)
        if not resp.ok: return None
        data = resp.json()
        return base64.b64decode(data["image_base64"]) if "image_base64" in data else None
    except Exception as e:
        logger.error(f"Lỗi lấy ảnh vệ tinh: {e}")
        return None

@st.cache_data(ttl=1800, show_spinner=False)
def get_satellite_image_bbox_cached(bbox_coords_ui, cloud, days, upscale):
    return get_satellite_image_bbox(bbox_coords_ui, cloud, days, upscale)

def run_ai_segmentation(image_data: bytes, bbox_coords_ui: List[List[float]], width: int, height: int) -> List[Dict]:
    if not ROBOFLOW_API_KEY: return []
    temp_dir = os.path.join("/tmp", "terrasync")
    os.makedirs(temp_dir, exist_ok=True)
    tmp_path = os.path.join(temp_dir, f"{uuid.uuid4()}.png")
    with open(tmp_path, "wb") as f:
        f.write(image_data)
    
    try:
        client = InferenceHTTPClient(api_url="https://serverless.roboflow.com", api_key=ROBOFLOW_API_KEY)
        result = client.run_workflow(workspace_name="tham-hoa-thin-nhin", workflow_id="detect-count-and-visualize-2", images={"image": tmp_path})
        
        detected = []
        if result and isinstance(result, list):
            preds = result[0].get("predictions", [])
            for pred in preds:
                pts = pred.get("points") or pred.get("polygon")
                if not pts: continue
                geo_poly = pixel_to_geo_bbox(pts, bbox_coords_ui, width, height)
                area_ha = calculate_polygon_area(geo_poly)
                detected.append({
                    "polygon": geo_poly,
                    "confidence": float(pred.get("confidence", 0.0)),
                    "area_hectares": area_ha,
                    "crop_type_suggestion": pred.get("class", "Unknown")
                })
        return detected
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return []
    finally:
        if os.path.exists(tmp_path): os.remove(tmp_path)

# --- CALLBACKS ---
def update_main_location():
    if st.session_state.temp_lat is not None:
        st.session_state.lat = st.session_state.temp_lat
        st.session_state.lon = st.session_state.temp_lon
        st.session_state.temp_lat = None
        st.session_state.temp_lon = None
        st.toast("✅ Đã cập nhật vị trí trung tâm thành công!", icon="📍")

# --- GIAO DIỆN CHÍNH ---

def render_add_field():
    st.title("🌾 Thêm Vườn Mới (Sentinel-4P)")
    
    defaults = {
        "lat": 20.450123, "lon": 106.325678,
        "location_confirmed": False,
        "draw_selection": "Chưa chọn",
        "edit_mode": False,
        "source": None,
        "polygon": None,
        "detected_fields": None,
        "temp_lat": None, 
        "temp_lon": None,
        "field_name_input": ""
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # ============================================================
    # BƯỚC 1: CHỌN VỊ TRÍ TRUNG TÂM
    # ============================================================
    st.subheader("📍 Bước 1: Chọn vị trí trung tâm")
    st.info("💡 **Hướng dẫn:** Click chuột vào bản đồ để chọn điểm mới. Nhấn **'Xác nhận'** để lưu.")

    col_map, col_info = st.columns([2, 1])

    with col_map:
        if st.session_state.temp_lat is not None:
            map_center = [st.session_state.temp_lat, st.session_state.temp_lon]
            zoom_lv = 17
        else:
            map_center = [st.session_state.lat, st.session_state.lon]
            zoom_lv = 16

        m = folium.Map(
            location=map_center, 
            zoom_start=zoom_lv, 
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri World Imagery'
        )
        
        folium.Marker(
            [st.session_state.lat, st.session_state.lon],
            popup="Vị trí Vườn (Đã lưu)",
            icon=folium.Icon(color='red', icon='home'),
        ).add_to(m)

        if st.session_state.temp_lat is not None:
            folium.Marker(
                [st.session_state.temp_lat, st.session_state.temp_lon],
                popup="Vị trí mới chọn",
                icon=folium.Icon(color='blue', icon='check', prefix='fa'),
            ).add_to(m)

        map_data = st_folium(
            m, 
            height=400, 
            width="100%", 
            key="center_map", 
            returned_objects=["last_clicked"]
        )

    if map_data and map_data.get("last_clicked"):
        clicked = map_data["last_clicked"]
        click_lat = float(clicked["lat"])
        click_lon = float(clicked["lng"])
        
        current_temp = st.session_state.temp_lat if st.session_state.temp_lat else 0.0
        if abs(click_lat - current_temp) > 0.0000001:
            st.session_state.temp_lat = click_lat
            st.session_state.temp_lon = click_lon
            st.rerun()

    with col_info:
        st.markdown("### 🛠️ Tọa độ")
        display_lat = st.session_state.temp_lat if st.session_state.temp_lat is not None else st.session_state.lat
        display_lon = st.session_state.temp_lon if st.session_state.temp_lon is not None else st.session_state.lon

        input_lat = st.number_input("Vĩ độ (Lat)", value=float(display_lat), format="%.6f", step=0.00001, key="input_lat")
        input_lon = st.number_input("Kinh độ (Lon)", value=float(display_lon), format="%.6f", step=0.00001, key="input_lon")

        if abs(input_lat - float(display_lat)) > 0.0000001 or abs(input_lon - float(display_lon)) > 0.0000001:
            st.session_state.temp_lat = input_lat
            st.session_state.temp_lon = input_lon
            st.rerun()

        st.divider()
        
        if st.session_state.temp_lat is not None:
            st.info("Đang chọn điểm mới")
            st.button("🔄 Xác nhận vị trí này", type="primary", on_click=update_main_location)
        else:
            st.caption("Đang hiển thị vị trí đã lưu.")

        st.divider()
        st.text_input("Đặt tên vườn", key="field_name_input")
        
        if st.button("Tiếp tục sang Bước 2 ➡️"):
            if not st.session_state.field_name_input:
                st.error("Vui lòng nhập tên vườn trước.")
            else:
                st.session_state.location_confirmed = True
                st.rerun()

    st.divider()

    # ============================================================
    # BƯỚC 2: VẼ RANH GIỚI
    # ============================================================
    if not st.session_state.location_confirmed:
        return

    st.subheader("🎯 Bước 2: Xác định ranh giới")
    
    tab1, tab2 = st.tabs(["Vẽ Thủ Công", "AI Phát Hiện (Sentinel-2)"])
    
    with tab1:
        if st.button("Kích hoạt chế độ vẽ thủ công"):
            st.session_state.draw_selection = "manual"
            st.session_state.source = "manual"
        
        if st.session_state.draw_selection == "manual":
            draw_m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=18,
                                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
            
            folium.Marker([st.session_state.lat, st.session_state.lon], popup="Tâm", icon=folium.Icon(color='green', icon='star')).add_to(draw_m)

            plugins.Draw(
                draw_options={'polygon': True, 'rectangle': False, 'circle': False, 'marker': False, 'polyline': False},
                edit_options={'edit': True, 'remove': True}
            ).add_to(draw_m)
            
            drawn_data = st_folium(draw_m, width=700, height=400, key="draw_map")
            if drawn_data and drawn_data.get("last_active_drawing"):
                geom = drawn_data["last_active_drawing"]["geometry"]
                if geom["type"] == "Polygon":
                    coords = geom["coordinates"][0]
                    st.session_state.polygon = [[c[1], c[0]] for c in coords]
                    st.success("Đã lưu hình vẽ thủ công.")

    with tab2:
        st.markdown("Vẽ một vùng chữ nhật bao quanh vườn để AI tự tách thửa.")
        ai_m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=18,
                          tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
        
        folium.Marker([st.session_state.lat, st.session_state.lon], popup="Tâm", icon=folium.Icon(color='green', icon='star')).add_to(ai_m)

        plugins.Draw(
            draw_options={'rectangle': True, 'polygon': False, 'circle': False, 'marker': False},
            edit_options={'edit': False, 'remove': True}
        ).add_to(ai_m)
        
        ai_data = st_folium(ai_m, width=700, height=400, key="ai_map")
        
        if ai_data and ai_data.get("last_active_drawing"):
            geom = ai_data["last_active_drawing"]["geometry"]
            if geom["type"] == "Polygon":
                rect_coords = geom["coordinates"][0]
                bbox = [[c[1], c[0]] for c in rect_coords]
                
                if st.button("🚀 Chạy AI Phân Tích"):
                    with st.spinner("Đang tải ảnh vệ tinh và phân tích..."):
                        img_bytes = get_satellite_image_bbox_cached(bbox, 70, 100, 1)
                        if img_bytes:
                            try:
                                img = Image.open(io.BytesIO(img_bytes))
                                w, h = img.size
                                results = run_ai_segmentation(img_bytes, bbox, w, h)
                                if results:
                                    st.session_state.detected_fields = results
                                    st.session_state.source = "ai"
                                    st.success(f"Tìm thấy {len(results)} vùng trồng.")
                                else:
                                    st.error("AI không tìm thấy ruộng nào trong vùng này.")
                            except Exception as e:
                                st.error(f"Lỗi xử lý ảnh: {e}")
                        else:
                            st.error("Không lấy được ảnh vệ tinh.")

        if st.session_state.get("detected_fields"):
            opts = [f"Vùng {i+1} - {d['area_hectares']:.2f} ha ({d['crop_type_suggestion']})" for i, d in enumerate(st.session_state.detected_fields)]
            sel_idx = st.selectbox("Chọn vùng kết quả:", range(len(opts)), format_func=lambda x: opts[x])
            
            if st.button("Áp dụng vùng này"):
                st.session_state.polygon = st.session_state.detected_fields[sel_idx]["polygon"]
                st.session_state.ai_confidence = st.session_state.detected_fields[sel_idx]["confidence"]

    # ============================================================
    # BƯỚC 3: CHI TIẾT & LƯU (ĐÃ BỎ FORM ĐỂ CẬP NHẬT REAL-TIME)
    # ============================================================
    if st.session_state.polygon:
        st.divider()
        st.subheader("📝 Bước 3: Thông tin chi tiết & Lưu")
        
        area = calculate_polygon_area(st.session_state.polygon)
        st.metric("Diện tích tính toán", f"{area:.2f} ha")

        # --- SỬA ĐỔI: KHÔNG DÙNG ST.FORM Ở ĐÂY ---
        c1, c2 = st.columns(2)
        with c1:
            # Tên vườn đã nhập ở bước 1
            final_name = st.text_input("Tên vườn (Xác nhận lại)", value=st.session_state.get("field_name_input", ""))
            
            try:
                crop_list = crop_db.get("crops")
                crop_names = [c["name"] for c in crop_list]
            except:
                crop_names = []
                st.error("Không đọc được dữ liệu cropdb.")

            # Selectbox nằm ngoài form -> Rerun ngay khi chọn -> Cập nhật Info bên phải
            selected_crop_name = st.selectbox("Loại cây trồng", crop_names)
            
            stage_map = {
                "Ươm (Initial)": "initial",
                "Phát triển (Development)": "development",
                "Giữa mùa/Ra hoa (Mid Season)": "mid_season",
                "Cuối mùa/Thu hoạch (Late Season)": "late_season"
            }
            selected_stage_label = st.selectbox("Giai đoạn phát triển", list(stage_map.keys()))
            selected_stage_key = stage_map[selected_stage_label]

        with c2:
            # Phần hiển thị thông tin sẽ tự động cập nhật
            if selected_crop_name:
                crop_info = next((c for c in crop_list if c["name"] == selected_crop_name), None)
                if crop_info:
                    kc = crop_info["water_needs"].get(selected_stage_key, 0)
                    days = crop_info["growth_stages"].get(selected_stage_key, 0)
                    temp_min = crop_info["warnings"]["nhiet_do"]["min"]
                    temp_max = crop_info["warnings"]["nhiet_do"]["max"]
                    
                    st.info(f"""
                    **Thông tin {selected_crop_name}:**
                    - Hệ số nước ($K_c$): **{kc}**
                    - Thời gian giai đoạn: {days} ngày
                    - Nhiệt độ tối ưu: {temp_min}°C - {temp_max}°C
                    """)
        
        # Nút Lưu nằm ngoài cùng
        if st.button("Lưu Vườn Vào Hệ Thống", type="primary"):
            if not final_name:
                st.error("Vui lòng nhập tên vườn.")
            else:
                new_field = {
                    "id": str(uuid.uuid4()),
                    "name": final_name,
                    "crop": selected_crop_name,
                    "crop_call_name": crop_info.get("call_name", "unknown"),
                    "area": area,
                    "polygon": st.session_state.polygon,
                    "center": [st.session_state.lat, st.session_state.lon],
                    "stage": selected_stage_key,
                    "status": "normal",
                    "created_at": datetime.now().isoformat(),
                    "user_email": getattr(st.user, "email", "demo_user@sentinel4p.com")
                }
                
                if st.session_state.source == "ai":
                    new_field["ai_confidence"] = st.session_state.get("ai_confidence", 0)

                if db.add("fields", new_field):
                    st.balloons()
                    st.success(f"Đã thêm vườn '{final_name}' thành công!")
                    
                    try:
                        water = predict_water_needs(new_field, None)
                        st.write(f"💧 Dự báo nhu cầu tưới hôm nay: **{water:.2f} lít**")
                    except:
                        pass
                        
                    st.session_state.polygon = None
                    st.session_state.location_confirmed = False
                else:
                    st.error("Lỗi khi lưu vào cơ sở dữ liệu.")