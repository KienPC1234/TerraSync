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

from database import db, crop_db
from inference_sdk import InferenceHTTPClient
from utils import predict_water_needs


@st.cache_resource
def load_config():
    config_path = Path(".streamlit/appcfg.toml")
    if not config_path.exists():
        st.error(
            f"Cảnh báo: Không tìm thấy file cấu hình tại '{config_path}'. Sử dụng giá trị mặc định.")
        return {}
    try:
        return toml.load(config_path)
    except Exception as e:
        st.error(f"Lỗi khi đọc file cấu hình: {e}. Sử dụng giá trị mặc định.")
        return {}


config = load_config()
api_cfg = config.get("api", {})

API_URL = api_cfg.get("aifield_url", "http://172.24.193.209:9990")
ROBOFLOW_API_KEY = st.secrets.get("roboflow", {}).get("api_key")
REQUEST_TIMEOUT = api_cfg.get("request_timeout", 120)
MAX_IMAGE_BYTES = api_cfg.get("max_image_bytes", 200 * 1024 * 1024)

_session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[
        429,
        500,
        502,
        503,
        504])
_session.mount("https://", HTTPAdapter(max_retries=retries))
_session.mount("http://", HTTPAdapter(max_retries=retries))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("add_field_app")


def safe_post_json(
        url: str,
        json_data: dict,
        timeout: int = REQUEST_TIMEOUT) -> requests.Response:
    resp = _session.post(url, json=json_data, timeout=timeout)
    return resp


def ensure_envs():
    if not ROBOFLOW_API_KEY:
        logger.warning("ROBOFLOW_API_KEY not set — Roboflow calls may fail.")


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
    return float(area_m2 / 10000.0)


def pixel_to_geo_bbox(points: List[dict],
                      bbox_coords: List[List[float]],
                      img_width: int,
                      img_height: int) -> List[List[float]]:
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


def convert_ui_bbox_to_backend(
        bbox_ui: List[List[float]]) -> List[List[float]]:
    out = []
    for p in bbox_ui:
        if len(p) != 2:
            raise ValueError("Each bbox point must be [lat, lon]")
        out.append([float(p[1]), float(p[0])])
    return out


@st.cache_data(ttl=60 * 30, show_spinner=False)
def get_satellite_image_bbox_cached(
        bbox_coords_ui: List[List[float]], cloud: float = 70.0, days: int = 100, upscale: int = 1) -> Optional[bytes]:
    return get_satellite_image_bbox(
        bbox_coords_ui,
        cloud=cloud,
        days=days,
        upscale=upscale)


def get_satellite_image_bbox(bbox_coords_ui: List[List[float]],
                             cloud: float = 70.0,
                             days: int = 100,
                             upscale: int = 1) -> Optional[bytes]:
    if not isinstance(bbox_coords_ui, list) or len(bbox_coords_ui) < 3:
        raise ValueError(
            "bbox_coords must be a list of at least 3 [lat, lon] points")

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
        raise Exception(f"Không thể yêu cầu ảnh vệ tinh: {e}")

    if not resp.ok:
        text = resp.text[:1000] if resp.text else str(resp.status_code)
        raise Exception(f"Lỗi backend {resp.status_code}: {text}")

    data = resp.json()
    if "image_base64" not in data:
        raise Exception(
            "Backend trả về phản hồi không mong muốn (thiếu image_base64)")

    image_bytes = base64.b64decode(data["image_base64"])
    if len(image_bytes) > MAX_IMAGE_BYTES:
        logger.warning("Image bytes larger than MAX limit")
    return image_bytes


def run_ai_segmentation(image_data: bytes,
                        bbox_coords_ui: List[List[float]],
                        width: int,
                        height: int) -> List[Dict[str,
                                                  Any]]:
    ensure_envs()
    temp_dir = os.path.join("/tmp", "terrasync")
    os.makedirs(temp_dir, exist_ok=True)
    tmp_path = os.path.join(temp_dir, f"{uuid.uuid4()}.png")
    with open(tmp_path, "wb") as f:
        f.write(image_data)

    try:
        client = InferenceHTTPClient(
            api_url="https://serverless.roboflow.com",
            api_key=ROBOFLOW_API_KEY)
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
            pts = pred.get("points") or pred.get(
                "polygon") or pred.get("bbox_points")
            conf = pred.get("confidence") or pred.get("score") or 0.0
            cls = pred.get("class") or pred.get("label") or "Không xác định"
            if not pts:
                continue
            try:
                geo_poly = pixel_to_geo_bbox(
                    pts, bbox_coords_ui, width, height)
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
        raise Exception(f"Phân đoạn AI thất bại: {e}")
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def parse_map_data_for_marker(map_data: dict,
                              fallback_lat: float,
                              fallback_lon: float) -> Tuple[Optional[float],
                                                            Optional[float]]:
    if not map_data:
        return None, None

    center = map_data.get("center")
    if center:
        if isinstance(center, dict):
            lat = center.get("lat") or center.get(
                "latitude") or center.get("Lat")
            lon = center.get("lng") or center.get(
                "lon") or center.get("longitude") or center.get("Lon")
            if lat is not None and lon is not None:
                return float(lat), float(lon)
        elif isinstance(center, (list, tuple)) and len(center) >= 2:
            return float(center[0]), float(center[1])

    last = map_data.get("last_object_clicked")
    if last and isinstance(last, dict):
        loc = last.get("latlng") or last.get("latLng") or last.get(
            "location") or last.get("geometry")
        if loc:
            if isinstance(loc, dict):
                lat = loc.get("lat") or loc.get("latitude")
                lon = loc.get("lng") or loc.get("lon") or loc.get("longitude")
                if lat is not None and lon is not None:
                    return float(lat), float(lon)
            elif isinstance(loc, (list, tuple)) and len(loc) >= 2:
                return float(loc[0]), float(loc[1])
        if last.get("geometry") and isinstance(last["geometry"], dict):
            geom = last["geometry"]
            coords = geom.get("coordinates")
            if coords and isinstance(
                    coords, (list, tuple)) and len(coords) >= 2:
                return float(coords[1]), float(coords[0])

    objs = map_data.get("all_objects")
    if objs and isinstance(objs, list) and len(objs) > 0:
        obj0 = objs[0]
        if isinstance(obj0, dict):
            loc = obj0.get("location") or obj0.get(
                "latlng") or obj0.get("geometry")
            if loc:
                if isinstance(loc, dict):
                    lat = loc.get("lat") or loc.get("latitude")
                    lon = loc.get("lng") or loc.get(
                        "lon") or loc.get("longitude")
                    if lat is not None and lon is not None:
                        return float(lat), float(lon)
                elif isinstance(loc, (list, tuple)) and len(loc) >= 2:
                    return float(loc[0]), float(loc[1])
            if obj0.get("geometry") and isinstance(obj0["geometry"], dict):
                coords = obj0["geometry"].get("coordinates")
                if coords and isinstance(
                        coords, (list, tuple)) and len(coords) >= 2:
                    return float(coords[1]), float(coords[0])

    bounds = map_data.get("bounds")
    if bounds and isinstance(bounds, dict):
        ne = bounds.get("northEast") or bounds.get(
            "north_east") or bounds.get("ne")
        sw = bounds.get("southWest") or bounds.get(
            "south_west") or bounds.get("sw")
        if ne and sw and isinstance(ne, dict) and isinstance(sw, dict):
            lat = (ne.get("lat") + sw.get("lat")) / 2.0
            lon = (ne.get("lng") + sw.get("lng")) / 2.0
            return float(lat), float(lon)

    return None, None


def render_add_field():
    st.title("🌾 Thêm vườn mới")
    st.markdown(
        "Đặt vị trí trung tâm, vẽ hoặc sử dụng AI để phát hiện ranh giới vườn, sau đó lưu lại.")

    if not hasattr(st, "user") or not getattr(st.user, "is_logged_in", False):
        st.error("Vui lòng đăng nhập để thêm vườn")
        return
    user_email = st.user.email

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

    st.subheader("📍 Bước 1 — Đặt vị trí trung tâm")
    st.markdown("Kéo ghim màu đỏ hoặc xác nhận tọa độ. Bản đồ được hiển thị trước để chúng tôi có thể ghi lại thao tác kéo ghim một cách an toàn.")

    map_lat = float(st.session_state.lat)
    map_lon = float(st.session_state.lon)
    m = folium.Map(
        location=[
            map_lat,
            map_lon],
        zoom_start=18,
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri World Imagery')
    folium.Marker([map_lat, map_lon], popup="Kéo tôi đến trung tâm",
                  icon=folium.Icon(color='red'), draggable=True).add_to(m)

    map_data = st_folium(
        m,
        width=700,
        height=400,
        key="center_map",
        returned_objects=[
            "all_objects",
            "last_object_clicked",
            "center",
            "bounds"])

    new_lat, new_lon = parse_map_data_for_marker(map_data, map_lat, map_lon)
    if new_lat is not None and new_lon is not None:
        if abs(new_lat -
               st.session_state.lat) > 1e-7 or abs(new_lon -
                                                   st.session_state.lon) > 1e-7:
            st.session_state["lat"] = float(new_lat)
            st.session_state["lon"] = float(new_lon)
            st.success(
                f"📍 Trung tâm đã cập nhật: {
                    new_lat:.6f}, {
                    new_lon:.6f}")

    col1, col2, col3 = st.columns([2, 2, 3])
    with col1:
        st.number_input(
            "Vĩ độ",
            value=st.session_state.lat,
            format="%.6f",
            key="lat")
    with col2:
        st.number_input(
            "Kinh độ",
            value=st.session_state.lon,
            format="%.6f",
            key="lon")
    with col3:
        field_name = st.text_input(
            "Tên vườn",
            placeholder="Vườn A...",
            key="field_name")

    if st.button("Xác nhận Vị trí & Tiếp tục", key="confirm_loc"):
        st.session_state.location_confirmed = True

    st.divider()

    if not st.session_state.location_confirmed:
        st.info("👆 Nhấn 'Xác nhận Vị trí & Tiếp tục' để mở Bước 2.")
        return

    st.subheader("🎯 Bước 2 — Xác định ranh giới vườn (Vẽ hoặc AI)")
    has_polygon = st.session_state.polygon is not None
    is_ai_complete = (st.session_state.source ==
                      "ai" and has_polygon and not st.session_state.edit_mode)

    if not has_polygon:
        mode = st.selectbox("Chọn chế độ:",
                            ["Chưa chọn",
                             "Vẽ thủ công (Đa giác)",
                             "Phát hiện bằng AI (Hình chữ nhật)"],
                            key="draw_selection")
        if mode == "Vẽ thủ công (Đa giác)":
            st.markdown("**🖍️ Vẽ thủ công**: Vẽ một đa giác xung quanh vườn.")
            draw_m = folium.Map(
                location=[
                    st.session_state.lat,
                    st.session_state.lon],
                zoom_start=18,
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attr='Esri')
            folium.Marker([st.session_state.lat, st.session_state.lon],
                          popup="Tâm", icon=folium.Icon(color="green")).add_to(draw_m)
            plugins.Draw(
                draw_options={
                    'polygon': True,
                    'rectangle': False,
                    'polyline': False,
                    'circle': False,
                    'marker': False},
                edit_options={
                    'edit': False,
                    'remove': True}).add_to(draw_m)

            drawn_data = st_folium(
                draw_m,
                width=700,
                height=400,
                key="draw_map",
                returned_objects=["last_active_drawing"])
            if drawn_data and drawn_data.get("last_active_drawing"):
                drawing = drawn_data["last_active_drawing"]
                geom = drawing.get("geometry", {})
                if geom.get("type") == "Polygon":
                    coords = geom.get("coordinates", [[]])[0]
                    st.session_state.polygon = [[c[1], c[0]] for c in coords]
                    st.session_state.source = "manual"
                    st.success("✅ Đã lưu đa giác (vẽ thủ công).")

        elif mode == "Phát hiện bằng AI (Hình chữ nhật)":
            st.markdown(
                "**🤖 Phát hiện bằng AI**: Vẽ một hình chữ nhật (bbox) sau đó nhấn 'Phát hiện AI'.")
            ai_map = folium.Map(
                location=[
                    st.session_state.lat,
                    st.session_state.lon],
                zoom_start=18,
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attr='Esri')
            folium.Marker([st.session_state.lat,
                           st.session_state.lon],
                          popup="Tâm").add_to(ai_map)
            plugins.Draw(
                draw_options={
                    'rectangle': True,
                    'polygon': False,
                    'polyline': False,
                    'circle': False,
                    'marker': False},
                edit_options={
                    'edit': False,
                    'remove': True}).add_to(ai_map)
            ai_data = st_folium(
                ai_map,
                width=700,
                height=400,
                key="ai_draw_map",
                returned_objects=["last_active_drawing"])
            if ai_data and ai_data.get("last_active_drawing"):
                drawing = ai_data["last_active_drawing"]
                geom = drawing.get("geometry", {})
                if geom.get("type") == "Polygon":
                    coords = geom.get("coordinates", [[]])[0]
                    st.session_state.ai_bbox = [[c[1], c[0]] for c in coords]
                    st.success("✅ Đã vẽ bbox cho AI.")

            if st.button(
                "Phát hiện AI",
                    key="detect_ai") and st.session_state.get("ai_bbox"):
                with st.spinner("Đang gọi backend lấy ảnh và chạy AI..."):
                    try:
                        img_bytes = get_satellite_image_bbox_cached(
                            st.session_state.ai_bbox, cloud=70.0, days=100, upscale=1)
                        if not img_bytes:
                            st.error("Không nhận được ảnh từ backend.")
                        else:
                            img = Image.open(
                                io.BytesIO(img_bytes)).convert("RGB")
                            st.image(
                                img, caption="Ảnh vệ tinh", use_container_width=True)
                            w, h = img.size
                            fields = run_ai_segmentation(
                                img_bytes, st.session_state.ai_bbox, w, h)
                            if fields:
                                st.session_state.detected_fields = fields
                                st.session_state.source = "ai"
                                st.session_state.polygon = fields[0]["polygon"]
                                st.session_state.ai_confidence = fields[0]["confidence"]
                                st.session_state.lat = float(
                                    np.mean([p[0] for p in st.session_state.polygon]))
                                st.session_state.lon = float(
                                    np.mean([p[1] for p in st.session_state.polygon]))
                                st.success(
                                    f"Phát hiện {
                                        len(fields)} vùng. Hiển thị vùng đầu tiên để chỉnh sửa.")
                            else:
                                st.error("AI không phát hiện vùng nào.")
                    except Exception as e:
                        st.error(f"Lỗi Phát hiện AI: {e}")

        else:
            st.info("Chọn một chế độ để tiếp tục.")
    elif is_ai_complete:
        st.markdown("**🌿 Chọn kết quả AI**")
        det = st.session_state.detected_fields or []
        if det:
            idx = st.selectbox(
                "Chọn vườn:",
                list(
                    range(
                        len(det))),
                format_func=lambda i: f"Vườn {
                    i +
                    1} — {
                    det[i]['crop_type_suggestion']} ({
                        det[i]['area_hectares']:.2f} ha, {
                            det[i]['confidence'] *
                    100:.1f}%)")
            selected = det[idx]
            center_lat = float(np.mean([p[0] for p in selected["polygon"]]))
            center_lon = float(np.mean([p[1] for p in selected["polygon"]]))
            show_map = folium.Map(
                location=[
                    center_lat,
                    center_lon],
                zoom_start=18,
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attr='Esri')
            for i, f in enumerate(det):
                color = "green" if i == idx else "blue"
                folium.Polygon(
                    f["polygon"],
                    color=color,
                    fill=True,
                    fill_opacity=0.3,
                    popup=f"Vườn {
                        i + 1}").add_to(show_map)
            st_folium(show_map, width=700, height=400)
            if st.button("Áp dụng vùng này"):
                st.session_state.polygon = selected["polygon"]
                st.session_state.ai_confidence = selected["confidence"]
                st.session_state.lat = center_lat
                st.session_state.lon = center_lon
                st.session_state.edit_mode = True
                st.success("Áp dụng vùng AI. Bạn có thể chỉnh sửa (Bước 2).")
    else:
        st.markdown("**✏️ Chỉnh sửa đa giác**")
        edit_map = folium.Map(
            location=[
                st.session_state.lat,
                st.session_state.lon],
            zoom_start=18,
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri')
        folium.Marker([st.session_state.lat, st.session_state.lon],
                      popup="Tâm").add_to(edit_map)
        if st.session_state.polygon:
            geojson = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {
                "type": "Polygon", "coordinates": [[[p[1], p[0]] for p in st.session_state.polygon]]}}]}
            GeoJson(geojson, style_function=lambda x: {
                    "color": "orange"}).add_to(edit_map)
        plugins.Draw(
            draw_options={
                'polygon': True,
                'rectangle': False,
                'polyline': False,
                'circle': False,
                'marker': False},
            edit_options={
                'edit': True,
                'remove': True}).add_to(edit_map)
        edit_data = st_folium(
            edit_map,
            width=700,
            height=400,
            key="edit_map",
            returned_objects=["all_drawings"])
        if edit_data and edit_data.get("all_drawings"):
            drawings = edit_data.get("all_drawings")
            if drawings:
                last = drawings[-1]
                geom = last.get("geometry", {})
                if geom.get("type") == "Polygon":
                    coords = geom.get("coordinates", [[]])[0]
                    st.session_state.polygon = [[c[1], c[0]] for c in coords]
                    st.success("Cập nhật đa giác thành công.")
        if st.button("Hoàn tất Chỉnh sửa", key="finish_edit"):
            st.session_state.edit_mode = False
            st.success("Lưu chỉnh sửa. Bước 3 đã mở.")

    if st.session_state.polygon and not st.session_state.edit_mode and st.session_state.draw_selection != "Chưa chọn":
        st.divider()
        st.subheader("📝 Bước 3 — Chi tiết vườn")
        area_ha = calculate_polygon_area(st.session_state.polygon)
        st.metric("Diện tích (ha)", f"{area_ha:.2f}")

        with st.form("field_form"):
            col1, col2 = st.columns(2)
            with col1:
                st.text_input(
                    "Tên vườn",
                    value=field_name or "",
                    key="confirm_name")
                available_crops = [crop['name']
                                   for crop in crop_db.get("crops")]
                crop_sel = st.selectbox(
                    "Loại cây trồng", available_crops, key="crop")
                stage = st.selectbox(
                    "Giai đoạn", [
                        "Ươm", "Phát triển", "Ra hoa", "Ra quả", "Trưởng thành"], key="stage")
            with col2:
                st.write("Thông số tưới")
                crop_info = next(
                    (c for c in crop_db.get("crops") if c.get("name") == crop_sel), None)
                if crop_info:
                    st.info(
                        f"Hệ số Kc cho giai đoạn '{stage}': {
                            crop_info['water_needs'].get(
                                stage.lower(), 1.0)}")

            submitted = st.form_submit_button("Thêm vườn", type="primary")
            if submitted:
                if not st.session_state.get("confirm_name"):
                    st.error("Vui lòng nhập tên vườn")
                else:
                    name_final = st.session_state.confirm_name
                    center_lat = float(
                        np.mean([p[0] for p in st.session_state.polygon]))
                    center_lon = float(
                        np.mean([p[1] for p in st.session_state.polygon]))
                    field_doc = {
                        "name": name_final,
                        "crop": crop_sel,
                        "area": area_ha,
                        "polygon": st.session_state.polygon,
                        "center": [center_lat, center_lon],
                        "lat": float(st.session_state.lat),
                        "lon": float(st.session_state.lon),
                        "stage": stage,
                        "status": "hydrated",
                        "created_at": datetime.utcnow().isoformat()
                    }
                    if st.session_state.source == "ai":
                        field_doc["detection_confidence"] = float(
                            st.session_state.ai_confidence or 0.0)
                    try:
                        ok = db.add("fields", field_doc)
                        if ok:
                            st.success(
                                "Thêm vườn thành công 🎉. Đang tính toán nhu cầu tưới ban đầu...")

                            try:
                                water_needs = predict_water_needs(
                                    field_doc, None)
                                update_data = {
                                    "today_water": water_needs,
                                    "time_needed": round(
                                        water_needs / 20,
                                        1) if water_needs > 0 else 0.0,
                                    "progress": 0}
                                db.update(
                                    "fields", {
                                        "id": field_doc['id']}, update_data)
                                st.info(
                                    f"Nhu cầu tưới ban đầu: {water_needs} lít, Thời gian: {
                                        update_data['time_needed']} giờ.")
                            except Exception as calc_e:
                                st.warning(
                                    f"Không thể tính toán nhu cầu tưới ban đầu: {calc_e}")

                            for k, v in defaults.items():
                                st.session_state[k] = v
                            st.session_state["field_name"] = ""
                            st.balloons()
                            if st.button("Xem danh sách vườn"):
                                st.session_state.navigate_to = "My Fields"
                        else:
                            st.error("Lỗi khi lưu vào DB.")
                    except Exception as e:
                        st.error(f"Lỗi DB khi lưu vườn: {e}")
    else:
        if not st.session_state.polygon:
            st.info("👆 Hoàn thành vẽ hoặc chọn vùng để mở Bước 3.")
