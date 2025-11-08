# file: add_field_app.py
"""
Streamlit app - Add Field (full rewrite)

Chú ý:
- Cấu hình:
    * API_URL: backend xử lý ảnh vệ tinh (mặc định dùng ENV API_URL hoặc URL cứng)
    * ROBOFLOW_API_KEY: (khuyến nghị đặt bằng biến môi trường)
- Cần module `database.py` với object `db` có phương thức:
    db.get(collection, query) -> list
    db.add(collection, doc) -> bool
    db.add_user_field(user_email, field_doc) -> bool

Cài đặt:
pip install streamlit folium streamlit-folium requests pillow numpy inference-sdk shapely rasterio pyproj
(Install theo nhu cầu — một số lib đã có trong môi trường của bạn)
"""
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

# Local imports (bạn đã có module này)
from database import db
from inference_sdk import InferenceHTTPClient  # nếu không có, stub hoặc xử lý ngoại lệ

# ------------------------
# Config & constants
# ------------------------
API_URL = os.getenv("API_URL", "http://172.24.193.209:9990")
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "u5p8jGeuTJwkNwIhPb2x")  # đặt env var cho an toàn
REQUEST_TIMEOUT = 120  # seconds
MAX_IMAGE_BYTES = 200 * 1024 * 1024  # 200MB guard

# Setup requests session with retries
_session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
_session.mount("https://", HTTPAdapter(max_retries=retries))
_session.mount("http://", HTTPAdapter(max_retries=retries))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("add_field_app")


# ------------------------
# Utilities
# ------------------------
def safe_post_json(url: str, json_data: dict, timeout: int = REQUEST_TIMEOUT) -> requests.Response:
    """POST with retries and consistent timeout"""
    resp = _session.post(url, json=json_data, timeout=timeout)
    return resp


def ensure_envs():
    if not ROBOFLOW_API_KEY:
        logger.warning("ROBOFLOW_API_KEY not set — Roboflow calls may fail.")


# ------------------------
# Geometry helpers
# ------------------------
def calculate_polygon_area(polygon: List[List[float]]) -> float:
    """
    polygon: list of [lat, lon] (degrees)
    returns: area in hectares (approx)
    """
    if not polygon or len(polygon) < 3:
        return 0.0
    # shoelace on (lon, lat)
    coords = [(p[1], p[0]) for p in polygon]
    n = len(coords)
    area = 0.0
    for i in range(n):
        x1, y1 = coords[i]
        x2, y2 = coords[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    area = abs(area) / 2.0
    # convert deg^2 to m^2 approximation
    avg_lat = np.mean([p[0] for p in polygon])
    avg_lat_rad = np.radians(avg_lat)
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * np.cos(avg_lat_rad)
    area_m2 = area * m_per_deg_lon * m_per_deg_lat
    return float(area_m2 / 10000.0)


def pixel_to_geo_bbox(points: List[dict], bbox_coords: List[List[float]], img_width: int, img_height: int) -> List[List[float]]:
    """
    Convert pixel polygon points to geo polygon.
    - points: list of dicts or lists with x,y
      Accepts formats: {'x':..., 'y':...} or {'X':..., 'Y':...} or [x,y]
    - bbox_coords: list of [lat, lon] (UI format)
    - img_width, img_height: int
    -> returns geo polygon list of [lat, lon]
    """
    # normalize bbox
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
        elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
            x, y = pt[0], pt[1]
        else:
            raise ValueError("Unsupported point format")
        x = float(x)
        y = float(y)
        x_norm = x / float(max(1, img_width))
        y_norm = y / float(max(1, img_height))
        lat = max_lat - y_norm * lat_range
        lon = min_lon + x_norm * lon_range
        geo.append([float(lat), float(lon)])
    return geo


# ------------------------
# Backend image fetcher
# ------------------------
def convert_ui_bbox_to_backend(bbox_ui: List[List[float]]) -> List[List[float]]:
    """
    UI uses [lat, lon] ordering. Backend expects [lon, lat].
    Convert list of points from UI->backend.
    """
    out = []
    for p in bbox_ui:
        if len(p) != 2:
            raise ValueError("Each bbox point must be [lat, lon]")
        out.append([float(p[1]), float(p[0])])
    return out


@st.cache_data(ttl=60 * 30, show_spinner=False)
def get_satellite_image_bbox_cached(bbox_coords_ui: List[List[float]], cloud: float = 70.0, days: int = 100, upscale: int = 1) -> Optional[bytes]:
    """Cached wrapper for get_satellite_image_bbox"""
    return get_satellite_image_bbox(bbox_coords_ui, cloud=cloud, days=days, upscale=upscale)


def get_satellite_image_bbox(bbox_coords_ui: List[List[float]], cloud: float = 70.0, days: int = 100, upscale: int = 1) -> Optional[bytes]:
    """
    Request backend to process satellite image.
    - bbox_coords_ui: list of [lat, lon] points (UI)
    Return image bytes or raise Exception.
    """
    if not isinstance(bbox_coords_ui, list) or len(bbox_coords_ui) < 3:
        raise ValueError("bbox_coords must be a list of at least 3 [lat, lon] points")

    # Convert to backend ordering [lon, lat]
    send_coords = convert_ui_bbox_to_backend(bbox_coords_ui)
    payload = {
        "coords": send_coords,
        "cloud": float(cloud),
        "days": int(days),
        "upscale": int(upscale)
    }

    url = f"{API_URL.rstrip('/')}/process_satellite_image"
    try:
        resp = safe_post_json(url, json_data=payload, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        logger.exception("Failed to POST to backend")
        raise Exception(f"Failed to request satellite image: {e}")

    if not resp.ok:
        text = resp.text[:1000] if resp.text else str(resp.status_code)
        raise Exception(f"Backend error {resp.status_code}: {text}")

    data = resp.json()
    if "image_base64" not in data:
        raise Exception("Backend returned unexpected response (missing image_base64)")

    image_bytes = base64.b64decode(data["image_base64"])
    if len(image_bytes) > MAX_IMAGE_BYTES:
        logger.warning("Image bytes larger than MAX limit")
    return image_bytes


# ------------------------
# AI segmentation (Roboflow) wrapper
# ------------------------
def run_ai_segmentation(image_data: bytes, bbox_coords_ui: List[List[float]], width: int, height: int) -> List[Dict[str, Any]]:
    """
    Run Roboflow inference workflow and convert predictions to geo polygons.
    - image_data: bytes of image
    - bbox_coords_ui: list [lat, lon] mapping to the image
    - width/height: image dimensions
    Returns list of detected fields: dict with 'polygon', 'confidence', 'area_hectares', 'crop_type_suggestion'
    """
    ensure_envs()
    temp_dir = os.path.join("/tmp", "terrasync")
    os.makedirs(temp_dir, exist_ok=True)
    tmp_path = os.path.join(temp_dir, f"{uuid.uuid4()}.png")
    with open(tmp_path, "wb") as f:
        f.write(image_data)

    try:
        client = InferenceHTTPClient(api_url="https://serverless.roboflow.com", api_key=ROBOFLOW_API_KEY)
        result = client.run_workflow(
            workspace_name="tham-hoa-thin-nhin",
            workflow_id="detect-count-and-visualize-2",
            images={"image": tmp_path},
            use_cache=True
        )
        detected = []
        if not result or not isinstance(result, list):
            return detected
        first = result[0]
        preds = first.get("predictions", [])
        for pred in preds:
            if not isinstance(pred, dict):
                continue
            pts = pred.get("points") or pred.get("polygon") or pred.get("bbox_points")
            conf = pred.get("confidence") or pred.get("score") or 0.0
            cls = pred.get("class") or pred.get("label") or "Unknown"
            if not pts:
                continue
            # normalize points format if needed
            try:
                geo_poly = pixel_to_geo_bbox(pts, bbox_coords_ui, width, height)
            except Exception as e:
                logger.exception("pixel->geo failed")
                continue
            area_ha = calculate_polygon_area(geo_poly)
            detected.append({
                "polygon": geo_poly,
                "confidence": float(conf),
                "area_hectares": float(area_ha),
                "crop_type_suggestion": cls
            })
        return detected
    except Exception as e:
        logger.exception("Roboflow inference failed")
        raise Exception(f"AI segmentation failed: {e}")
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


# ------------------------
# UI helpers
# ------------------------
def parse_map_data_for_marker(map_data: dict, fallback_lat: float, fallback_lon: float) -> Tuple[Optional[float], Optional[float]]:
    """
    Try to extract lat/lon from st_folium's returned map_data.
    Handles many possible shapes.
    Returns (lat, lon) or (None, None)
    """
    if not map_data:
        return None, None

    # 1) center
    center = map_data.get("center")
    if center:
        if isinstance(center, dict):
            lat = center.get("lat") or center.get("latitude") or center.get("Lat")
            lon = center.get("lng") or center.get("lon") or center.get("longitude") or center.get("Lon")
            if lat is not None and lon is not None:
                return float(lat), float(lon)
        elif isinstance(center, (list, tuple)) and len(center) >= 2:
            return float(center[0]), float(center[1])

    # 2) last_object_clicked
    last = map_data.get("last_object_clicked")
    if last and isinstance(last, dict):
        loc = last.get("latlng") or last.get("latLng") or last.get("location") or last.get("geometry")
        if loc:
            if isinstance(loc, dict):
                lat = loc.get("lat") or loc.get("latitude")
                lon = loc.get("lng") or loc.get("lon") or loc.get("longitude")
                if lat is not None and lon is not None:
                    return float(lat), float(lon)
            elif isinstance(loc, (list, tuple)) and len(loc) >= 2:
                return float(loc[0]), float(loc[1])
        # GeoJSON style
        if last.get("geometry") and isinstance(last["geometry"], dict):
            geom = last["geometry"]
            coords = geom.get("coordinates")
            if coords and isinstance(coords, (list, tuple)) and len(coords) >= 2:
                # coords may be [lon, lat]
                return float(coords[1]), float(coords[0])

    # 3) all_objects
    objs = map_data.get("all_objects")
    if objs and isinstance(objs, list) and len(objs) > 0:
        obj0 = objs[0]
        if isinstance(obj0, dict):
            loc = obj0.get("location") or obj0.get("latlng") or obj0.get("geometry")
            if loc:
                if isinstance(loc, dict):
                    lat = loc.get("lat") or loc.get("latitude")
                    lon = loc.get("lng") or loc.get("lon") or loc.get("longitude")
                    if lat is not None and lon is not None:
                        return float(lat), float(lon)
                elif isinstance(loc, (list, tuple)) and len(loc) >= 2:
                    return float(loc[0]), float(loc[1])
            if obj0.get("geometry") and isinstance(obj0["geometry"], dict):
                coords = obj0["geometry"].get("coordinates")
                if coords and isinstance(coords, (list, tuple)) and len(coords) >= 2:
                    return float(coords[1]), float(coords[0])

    # fallback: bounds center if present
    bounds = map_data.get("bounds")
    if bounds and isinstance(bounds, dict):
        # bounds may have northEast / southWest
        ne = bounds.get("northEast") or bounds.get("north_east") or bounds.get("ne")
        sw = bounds.get("southWest") or bounds.get("south_west") or bounds.get("sw")
        if ne and sw and isinstance(ne, dict) and isinstance(sw, dict):
            lat = (ne.get("lat") + sw.get("lat")) / 2.0
            lon = (ne.get("lng") + sw.get("lng")) / 2.0
            return float(lat), float(lon)

    return None, None


# ------------------------
# Main render function (full)
# ------------------------
def render_add_field():
    st.title("🌾 Add New Field")
    st.markdown("Set center, draw or use AI to detect field boundary, then save.")

    # Simple login guard - adapt to your auth
    if not hasattr(st, "user") or not getattr(st.user, "is_logged_in", False):
        st.error("Vui lòng đăng nhập để thêm field")
        return
    user_email = st.user.email

    # session defaults
    defaults = {
        "lat": 20.450123,
        "lon": 106.325678,
        "location_confirmed": False,
        "draw_selection": "Chưa chọn",
        "edit_mode": False,
        "source": None,
        "polygon": None,
        "detected_fields": None,
        "ai_confidence": None,
        "ai_bbox": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # ---------------- STEP 1 ----------------
    st.subheader("📍 Step 1 — Set Center Location")
    st.markdown("Drag the red pin or confirm the coordinate. Map is shown first so we can capture marker drag safely.")

    # --- 1) Draw map first (so we can parse map_data BEFORE creating widgets 'lat'/'lon') ---
    map_lat = float(st.session_state.lat)
    map_lon = float(st.session_state.lon)
    m = folium.Map(location=[map_lat, map_lon], zoom_start=18,
                   tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                   attr='Esri World Imagery')
    folium.Marker([map_lat, map_lon], popup="Kéo tôi đến trung tâm", icon=folium.Icon(color='red'), draggable=True).add_to(m)

    # request richer returned objects
    map_data = st_folium(m, width=700, height=400, key="center_map",
                         returned_objects=["all_objects", "last_object_clicked", "center", "bounds"])

    # --- 2) Parse new coords from map_data BEFORE we create input widgets ---
    new_lat, new_lon = parse_map_data_for_marker(map_data, map_lat, map_lon)
    if new_lat is not None and new_lon is not None:
        # only update if changed significantly to avoid noisy updates
        if abs(new_lat - st.session_state.lat) > 1e-7 or abs(new_lon - st.session_state.lon) > 1e-7:
            # safe: number_input with key 'lat'/'lon' not yet instantiated (we haven't created them below)
            st.session_state["lat"] = float(new_lat)
            st.session_state["lon"] = float(new_lon)
            # display user feedback
            st.success(f"📍 Center đã cập nhật: {new_lat:.6f}, {new_lon:.6f}")

    # --- 3) Now create the input widgets (they use the possibly-updated session_state values) ---
    col1, col2, col3 = st.columns([2, 2, 3])
    with col1:
        st.number_input("Vĩ độ (Latitude)", value=st.session_state.lat, format="%.6f", key="lat")
    with col2:
        st.number_input("Kinh độ (Longitude)", value=st.session_state.lon, format="%.6f", key="lon")
    with col3:
        field_name = st.text_input("Tên Field", placeholder="Vườn A...", key="field_name")

    # Confirm button to open next steps
    if st.button("Xác nhận Vị trí & Tiếp Tục", key="confirm_loc"):
        st.session_state.location_confirmed = True

    st.divider()

    if not st.session_state.location_confirmed:
        st.info("👆 Nhấn 'Xác nhận Vị trí & Tiếp Tục' để mở Step 2.")
        return

    # ---------------- Step 2 ----------------
    st.subheader("🎯 Step 2 — Define Field Boundary (Draw or AI)")
    has_polygon = st.session_state.polygon is not None
    is_ai_complete = (st.session_state.source == "ai" and has_polygon and not st.session_state.edit_mode)

    if not has_polygon:
        mode = st.selectbox("Chọn chế độ vẽ:", ["Chưa chọn", "Vẽ thủ công (Polygon)", "Phát hiện bằng AI (Rectangle)"], key="draw_selection")
        if mode == "Vẽ thủ công (Polygon)":
            st.markdown("**🖍️ Vẽ thủ công**: vẽ polygon quanh ruộng.")
            draw_m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=18,
                                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
            folium.Marker([st.session_state.lat, st.session_state.lon], popup="Tâm", icon=folium.Icon(color="green")).add_to(draw_m)
            plugins.Draw(draw_options={'polygon': True, 'rectangle': False, 'polyline': False, 'circle': False, 'marker': False},
                         edit_options={'edit': False, 'remove': True}).add_to(draw_m)

            drawn_data = st_folium(draw_m, width=700, height=400, key="draw_map", returned_objects=["last_active_drawing"])
            if drawn_data and drawn_data.get("last_active_drawing"):
                drawing = drawn_data["last_active_drawing"]
                geom = drawing.get("geometry", {})
                if geom.get("type") == "Polygon":
                    coords = geom.get("coordinates", [[]])[0]
                    st.session_state.polygon = [[c[1], c[0]] for c in coords]
                    st.session_state.source = "manual"
                    st.success("✅ Đã lưu polygon (vẽ thủ công).")

        elif mode == "Phát hiện bằng AI (Rectangle)":
            st.markdown("**🤖 Phát hiện bằng AI**: vẽ rectangle (bbox) rồi nhấn Detect AI.")
            ai_map = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=18,
                                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
            folium.Marker([st.session_state.lat, st.session_state.lon], popup="Tâm").add_to(ai_map)
            plugins.Draw(draw_options={'rectangle': True, 'polygon': False, 'polyline': False, 'circle': False, 'marker': False},
                         edit_options={'edit': False, 'remove': True}).add_to(ai_map)
            ai_data = st_folium(ai_map, width=700, height=400, key="ai_draw_map", returned_objects=["last_active_drawing"])
            if ai_data and ai_data.get("last_active_drawing"):
                drawing = ai_data["last_active_drawing"]
                geom = drawing.get("geometry", {})
                if geom.get("type") == "Polygon":
                    coords = geom.get("coordinates", [[]])[0]
                    # Save bbox in UI format [lat, lon]
                    st.session_state.ai_bbox = [[c[1], c[0]] for c in coords]
                    st.success("✅ Đã vẽ bbox cho AI.")

            if st.button("Detect AI", key="detect_ai") and st.session_state.get("ai_bbox"):
                with st.spinner("Đang gọi backend lấy ảnh và chạy AI..."):
                    try:
                        img_bytes = get_satellite_image_bbox_cached(st.session_state.ai_bbox, cloud=70.0, days=100, upscale=1)
                        if not img_bytes:
                            st.error("Không nhận được ảnh từ backend.")
                        else:
                            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                            st.image(img, caption="Ảnh Vệ Tinh", use_container_width=True)
                            w, h = img.size
                            fields = run_ai_segmentation(img_bytes, st.session_state.ai_bbox, w, h)
                            if fields:
                                st.session_state.detected_fields = fields
                                st.session_state.source = "ai"
                                # pick first automatically and enable edit
                                st.session_state.polygon = fields[0]["polygon"]
                                st.session_state.ai_confidence = fields[0]["confidence"]
                                # update center to polygon centroid
                                st.session_state.lat = float(np.mean([p[0] for p in st.session_state.polygon]))
                                st.session_state.lon = float(np.mean([p[1] for p in st.session_state.polygon]))
                                st.success(f"Phát hiện {len(fields)} vùng. Hiển thị vùng đầu tiên để chỉnh sửa.")
                            else:
                                st.error("AI không phát hiện vùng nào.")
                    except Exception as e:
                        st.error(f"Lỗi Detect AI: {e}")

        else:
            st.info("Chọn chế độ vẽ để tiếp tục.")
    elif is_ai_complete:
        st.markdown("**🌿 Chọn kết quả AI**")
        det = st.session_state.detected_fields or []
        if det:
            idx = st.selectbox("Chọn field:", list(range(len(det))),
                               format_func=lambda i: f"Field {i+1} — {det[i]['crop_type_suggestion']} ({det[i]['area_hectares']:.2f} ha, {det[i]['confidence']*100:.1f}%)")
            selected = det[idx]
            center_lat = float(np.mean([p[0] for p in selected["polygon"]]))
            center_lon = float(np.mean([p[1] for p in selected["polygon"]]))
            show_map = folium.Map(location=[center_lat, center_lon], zoom_start=18,
                                  tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
            for i, f in enumerate(det):
                color = "green" if i == idx else "blue"
                folium.Polygon(f["polygon"], color=color, fill=True, fill_opacity=0.3, popup=f"Field {i+1}").add_to(show_map)
            st_folium(show_map, width=700, height=400)
            if st.button("Áp Dụng vùng này"):
                st.session_state.polygon = selected["polygon"]
                st.session_state.ai_confidence = selected["confidence"]
                st.session_state.lat = center_lat
                st.session_state.lon = center_lon
                st.session_state.edit_mode = True
                st.success("Áp dụng vùng AI. Bạn có thể chỉnh sửa (Step 2).")
    else:
        # Edit mode (show polygon & allow redraw)
        st.markdown("**✏️ Chỉnh sửa polygon**")
        edit_map = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=18,
                              tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri')
        folium.Marker([st.session_state.lat, st.session_state.lon], popup="Tâm").add_to(edit_map)
        if st.session_state.polygon:
            geojson = {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[p[1], p[0]] for p in st.session_state.polygon]]}}]
            }
            GeoJson(geojson, style_function=lambda x: {"color": "orange"}).add_to(edit_map)
        plugins.Draw(draw_options={'polygon': True, 'rectangle': False, 'polyline': False, 'circle': False, 'marker': False},
                     edit_options={'edit': True, 'remove': True}).add_to(edit_map)
        edit_data = st_folium(edit_map, width=700, height=400, key="edit_map", returned_objects=["all_drawings"])
        if edit_data and edit_data.get("all_drawings"):
            drawings = edit_data.get("all_drawings")
            if drawings:
                last = drawings[-1]
                geom = last.get("geometry", {})
                if geom.get("type") == "Polygon":
                    coords = geom.get("coordinates", [[]])[0]
                    st.session_state.polygon = [[c[1], c[0]] for c in coords]
                    st.success("Cập nhật polygon thành công.")
        # finish edit
        if st.button("Xong Chỉnh Sửa", key="finish_edit"):
            st.session_state.edit_mode = False
            st.success("Lưu chỉnh sửa. Bước 3 đã mở.")

    # ---------------- Step 3 ----------------
    if st.session_state.polygon and not st.session_state.edit_mode and st.session_state.draw_selection != "Chưa chọn":
        st.divider()
        st.subheader("📝 Step 3 — Field Details")
        area_ha = calculate_polygon_area(st.session_state.polygon)
        st.metric("Diện tích (ha)", f"{area_ha:.2f}")

        with st.form("field_form"):
            col1, col2 = st.columns(2)
            with col1:
                st.text_input("Tên Field", value=field_name or "", key="confirm_name")
                available = get_available_crops(user_email)
                crop_options = available + ["Other"]
                crop_sel = st.selectbox("Loại Cây Trồng", crop_options, key="crop")
                stage = st.selectbox("Giai Đoạn", ["Seedling", "Vegetative", "Flowering", "Fruiting", "Maturity"], key="stage")
            with col2:
                custom_crop = st.text_input("Tên Cây Khác", placeholder="Durian...", key="custom_crop", disabled=(crop_sel != "Other"))
                crop_coeff = 1.0
                irr_eff = 85.0
                if crop_sel == "Other" and custom_crop:
                    ch = get_crop_characteristics(custom_crop)
                    st.info(f"Tham số (mặc định) cho {custom_crop}")
                    crop_coeff = st.number_input("Hệ số Kc", value=ch["crop_coefficient"], min_value=0.1, max_value=3.0, step=0.1, key="kc")
                    irr_eff = st.number_input("Hiệu suất tưới %", value=ch["irrigation_efficiency"], min_value=50, max_value=100, key="ie")
                else:
                    ch = get_crop_characteristics(crop_sel)
                    st.info(f"Tham số cho {crop_sel}")
                    crop_coeff = st.number_input("Hệ số Kc", value=ch["crop_coefficient"], min_value=0.1, max_value=3.0, step=0.1, key="kc")
                    irr_eff = st.number_input("Hiệu suất tưới %", value=ch["irrigation_efficiency"], min_value=50, max_value=100, key="ie")

            submitted = st.form_submit_button("Thêm Field", type="primary")
            if submitted:
                if not st.session_state.get("confirm_name"):
                    st.error("Nhập tên field")
                else:
                    name_final = st.session_state.confirm_name
                    actual_crop = custom_crop if crop_sel == "Other" and custom_crop else crop_sel
                    add_crop_if_not_exists(actual_crop, user_email)
                    center_lat = float(np.mean([p[0] for p in st.session_state.polygon]))
                    center_lon = float(np.mean([p[1] for p in st.session_state.polygon]))
                    field_doc = {
                        "name": name_final,
                        "crop": actual_crop,
                        "area": area_ha,
                        "polygon": st.session_state.polygon,
                        "center": [center_lat, center_lon],
                        "lat": float(st.session_state.lat),
                        "lon": float(st.session_state.lon),
                        "stage": stage,
                        "crop_coefficient": float(crop_coeff),
                        "irrigation_efficiency": float(irr_eff),
                        "status": "hydrated",
                        "created_at": datetime.utcnow().isoformat()
                    }
                    if st.session_state.source == "ai":
                        field_doc["detection_confidence"] = float(st.session_state.ai_confidence or 0.0)
                    try:
                        ok = db.add_user_field(user_email, field_doc)
                        if ok:
                            st.success("Thêm field thành công 🎉")
                            # reset states (only defaults)
                            for k, v in defaults.items():
                                st.session_state[k] = v
                            st.session_state["field_name"] = ""
                            st.balloons()
                            # navigate or show list
                            if st.button("Xem Fields"):
                                st.session_state.navigate_to = "My Fields"
                        else:
                            st.error("Lỗi lưu vào DB.")
                    except Exception as e:
                        st.error(f"Lỗi DB khi lưu field: {e}")
    else:
        if not st.session_state.polygon:
            st.info("👆 Hoàn thành vẽ hoặc pick vùng để mở Step 3.")


# ------------------------
# Crop DB helpers (from your original)
# ------------------------
CROP_DATABASE = {
    # --- Lúa & Ngũ cốc ---
    "Lúa": {
        "growth_rate": 0.8,
        "water_requirement": 120,
        "sun_requirement": 8,
        "crop_coefficient": 1.1,
        "irrigation_efficiency": 80,
        "planting_season": "Mùa mưa",
        "harvest_days": 120,
        "soil_type": "Đất thịt pha sét",
        "ph_range": "6.0-7.0"
    },
    "Ngô": {
        "growth_rate": 0.9,
        "water_requirement": 100,
        "sun_requirement": 10,
        "crop_coefficient": 1.0,
        "irrigation_efficiency": 85,
        "planting_season": "Mùa khô",
        "harvest_days": 90,
        "soil_type": "Đất cát pha",
        "ph_range": "6.0-7.5"
    },
    "Lúa mì": {
        "growth_rate": 0.85,
        "water_requirement": 90,
        "sun_requirement": 8,
        "crop_coefficient": 1.05,
        "irrigation_efficiency": 85,
        "planting_season": "Mùa lạnh",
        "harvest_days": 110,
        "soil_type": "Đất thịt nhẹ",
        "ph_range": "6.0-7.5"
    },
    "Khoai lang": {
        "growth_rate": 0.7,
        "water_requirement": 75,
        "sun_requirement": 8,
        "crop_coefficient": 0.85,
        "irrigation_efficiency": 80,
        "planting_season": "Mùa khô",
        "harvest_days": 100,
        "soil_type": "Đất cát pha",
        "ph_range": "5.5-6.5"
    },
    "Khoai tây": {
        "growth_rate": 0.8,
        "water_requirement": 85,
        "sun_requirement": 7,
        "crop_coefficient": 0.9,
        "irrigation_efficiency": 80,
        "planting_season": "Mùa lạnh",
        "harvest_days": 90,
        "soil_type": "Đất thịt nhẹ",
        "ph_range": "5.5-6.5"
    },

    # --- Rau củ ---
    "Cải bắp": {
        "growth_rate": 0.7,
        "water_requirement": 85,
        "sun_requirement": 6,
        "crop_coefficient": 0.9,
        "irrigation_efficiency": 85,
        "planting_season": "Mùa mát",
        "harvest_days": 70,
        "soil_type": "Đất thịt pha",
        "ph_range": "6.0-7.0"
    },
    "Cà chua": {
        "growth_rate": 0.9,
        "water_requirement": 100,
        "sun_requirement": 8,
        "crop_coefficient": 1.05,
        "irrigation_efficiency": 80,
        "planting_season": "Mùa khô",
        "harvest_days": 90,
        "soil_type": "Đất tơi xốp",
        "ph_range": "6.0-6.8"
    },
    "Dưa leo": {
        "growth_rate": 0.95,
        "water_requirement": 95,
        "sun_requirement": 9,
        "crop_coefficient": 1.1,
        "irrigation_efficiency": 80,
        "planting_season": "Mùa khô",
        "harvest_days": 60,
        "soil_type": "Đất phù sa",
        "ph_range": "6.0-7.0"
    },
    "Cà rốt": {
        "growth_rate": 0.8,
        "water_requirement": 80,
        "sun_requirement": 6,
        "crop_coefficient": 0.9,
        "irrigation_efficiency": 85,
        "planting_season": "Mùa lạnh",
        "harvest_days": 90,
        "soil_type": "Đất cát pha",
        "ph_range": "6.0-7.0"
    },
    "Rau muống": {
        "growth_rate": 0.95,
        "water_requirement": 120,
        "sun_requirement": 8,
        "crop_coefficient": 1.0,
        "irrigation_efficiency": 80,
        "planting_season": "Quanh năm",
        "harvest_days": 30,
        "soil_type": "Đất ẩm",
        "ph_range": "6.5-7.5"
    },

    # --- Cây ăn quả ---
    "Xoài": {
        "growth_rate": 0.85,
        "water_requirement": 100,
        "sun_requirement": 9,
        "crop_coefficient": 1.0,
        "irrigation_efficiency": 85,
        "planting_season": "Mùa khô",
        "harvest_days": 180,
        "soil_type": "Đất phù sa",
        "ph_range": "5.5-7.5"
    },
    "Cam": {
        "growth_rate": 0.9,
        "water_requirement": 110,
        "sun_requirement": 8,
        "crop_coefficient": 1.05,
        "irrigation_efficiency": 85,
        "planting_season": "Mùa mưa",
        "harvest_days": 240,
        "soil_type": "Đất tơi xốp",
        "ph_range": "5.5-6.5"
    },
    "Chuối": {
        "growth_rate": 1.0,
        "water_requirement": 140,
        "sun_requirement": 10,
        "crop_coefficient": 1.2,
        "irrigation_efficiency": 80,
        "planting_season": "Quanh năm",
        "harvest_days": 300,
        "soil_type": "Đất phù sa ẩm",
        "ph_range": "6.0-7.5"
    },
    "Sầu riêng": {
        "growth_rate": 0.9,
        "water_requirement": 150,
        "sun_requirement": 10,
        "crop_coefficient": 1.2,
        "irrigation_efficiency": 80,
        "planting_season": "Mùa khô",
        "harvest_days": 365,
        "soil_type": "Đất thịt pha cát",
        "ph_range": "6.0-7.0"
    },
    "Thanh long": {
        "growth_rate": 0.85,
        "water_requirement": 90,
        "sun_requirement": 10,
        "crop_coefficient": 1.1,
        "irrigation_efficiency": 80,
        "planting_season": "Mùa khô",
        "harvest_days": 180,
        "soil_type": "Đất cát pha",
        "ph_range": "6.0-7.0"
    },

    # --- Cây công nghiệp ---
    "Cà phê": {
        "growth_rate": 0.8,
        "water_requirement": 130,
        "sun_requirement": 9,
        "crop_coefficient": 1.1,
        "irrigation_efficiency": 80,
        "planting_season": "Mùa mưa",
        "harvest_days": 270,
        "soil_type": "Đất đỏ bazan",
        "ph_range": "5.5-6.5"
    },
    "Hồ tiêu": {
        "growth_rate": 0.75,
        "water_requirement": 120,
        "sun_requirement": 8,
        "crop_coefficient": 1.1,
        "irrigation_efficiency": 80,
        "planting_season": "Mùa mưa",
        "harvest_days": 365,
        "soil_type": "Đất đỏ bazan",
        "ph_range": "5.5-7.0"
    },
    "Chè": {
        "growth_rate": 0.8,
        "water_requirement": 100,
        "sun_requirement": 7,
        "crop_coefficient": 1.0,
        "irrigation_efficiency": 80,
        "planting_season": "Mùa mưa",
        "harvest_days": 210,
        "soil_type": "Đất đồi ẩm",
        "ph_range": "4.5-6.0"
    },
    "Mía": {
        "growth_rate": 0.9,
        "water_requirement": 140,
        "sun_requirement": 10,
        "crop_coefficient": 1.15,
        "irrigation_efficiency": 75,
        "planting_season": "Mùa khô",
        "harvest_days": 300,
        "soil_type": "Đất phù sa",
        "ph_range": "6.0-7.5"
    },

    # --- Cây gia vị & dược liệu ---
    "Gừng": {
        "growth_rate": 0.8,
        "water_requirement": 90,
        "sun_requirement": 7,
        "crop_coefficient": 0.9,
        "irrigation_efficiency": 80,
        "planting_season": "Mùa mưa",
        "harvest_days": 180,
        "soil_type": "Đất tơi xốp",
        "ph_range": "6.0-7.0"
    },
    "Nghệ": {
        "growth_rate": 0.75,
        "water_requirement": 85,
        "sun_requirement": 7,
        "crop_coefficient": 0.9,
        "irrigation_efficiency": 80,
        "planting_season": "Mùa mưa",
        "harvest_days": 200,
        "soil_type": "Đất cát pha",
        "ph_range": "6.0-7.0"
    },
    "Sả": {
        "growth_rate": 0.8,
        "water_requirement": 80,
        "sun_requirement": 8,
        "crop_coefficient": 0.9,
        "irrigation_efficiency": 80,
        "planting_season": "Quanh năm",
        "harvest_days": 150,
        "soil_type": "Đất cát pha",
        "ph_range": "5.5-7.5"
    },

    # --- Cây cảnh & cỏ ---
    "Hoa hồng": {
        "growth_rate": 0.7,
        "water_requirement": 70,
        "sun_requirement": 6,
        "crop_coefficient": 0.85,
        "irrigation_efficiency": 80,
        "planting_season": "Mùa mát",
        "harvest_days": 100,
        "soil_type": "Đất thịt nhẹ",
        "ph_range": "6.0-7.0"
    },
    "Cỏ sân vườn": {
        "growth_rate": 0.8,
        "water_requirement": 90,
        "sun_requirement": 7,
        "crop_coefficient": 0.8,
        "irrigation_efficiency": 85,
        "planting_season": "Quanh năm",
        "harvest_days": 45,
        "soil_type": "Đất thoát nước tốt",
        "ph_range": "6.0-7.5"
    }
}


def get_crop_characteristics(crop_name: str):
    if crop_name in CROP_DATABASE:
        return CROP_DATABASE[crop_name]
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
    try:
        existing = db.get("crops", {"name": crop_name, "user_email": user_email})
        if existing:
            return True
        characteristics = get_crop_characteristics(crop_name)
        crop_data = {"name": crop_name, **characteristics, "user_email": user_email, "created_at": datetime.utcnow().isoformat(), "is_ai_generated": crop_name not in CROP_DATABASE}
        return db.add("crops", crop_data)
    except Exception as e:
        logger.exception("DB error in add_crop_if_not_exists")
        return False


def get_available_crops(user_email: str) -> List[str]:
    try:
        user_crops = db.get("crops", {"user_email": user_email}) or []
        names = [c.get("name") for c in user_crops if c.get("name")]
        allc = list(CROP_DATABASE.keys())
        for n in names:
            if n not in allc:
                allc.append(n)
        return sorted(allc)
    except Exception:
        return sorted(list(CROP_DATABASE.keys()))

