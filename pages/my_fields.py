import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
from database import db, crop_db
from datetime import datetime, timezone
import logging
from utils import get_latest_telemetry_stats
import toml
from pathlib import Path

logger = logging.getLogger("my_fields_app")


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
irrigation_cfg = config.get('irrigation', {})
MOISTURE_MIN_THRESHOLD = irrigation_cfg.get('moisture_min_threshold', 25.0)
MOISTURE_MAX_THRESHOLD = irrigation_cfg.get('moisture_max_threshold', 55.0)
RAIN_THRESHOLD_MMH = irrigation_cfg.get('rain_threshold_mmh', 1.0)


def render_progress(value):
    value = int(value)
    color = "#28a745" if value >= 80 else "#ffc107" if value >= 30 else "#dc3545"
    html = f"""
    <div style="position: relative; width: 60px; height: 60px; margin: auto;">
        <svg viewBox="0 0 36 36" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; transform: rotate(-90deg);">
            <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#e9ecef" stroke-width="3" />
            <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="{color}" stroke-width="3" stroke-dasharray="{value}, 100" />
        </svg>
        <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 14px; font-weight: bold; color: #495057;">{value}%</div>
    </div>
    """
    return html


def get_field_data(user_email: str):
    user_fields = db.get("fields", {"user_email": user_email})
    fields = user_fields if user_fields else []

    hydration_jobs = {'completed': 0, 'active': 0, 'remaining': 0}

    for f in fields:
        progress = f.get('progress', 0)
        if progress == 100:
            hydration_jobs['completed'] += 1
        elif 0 < progress < 100:
            hydration_jobs['active'] += 1
        else:
            hydration_jobs['remaining'] += 1

    return fields, hydration_jobs


def get_available_crops() -> list[str]:
    try:
        crops = crop_db.get("crops")
        return sorted([c.get("name") for c in crops if c.get("name")])
    except Exception:
        return []


def run_field_update(user_email: str):
    fields = db.get("fields", {"user_email": user_email})
    if not fields:
        return 0

    updated_count = 0
    for field in fields:
        live_stats = get_latest_telemetry_stats(user_email, field.get('id'))

        if live_stats and live_stats.get("avg_moisture") is not None:
            avg_moisture = live_stats["avg_moisture"]
            rain_intensity = live_stats["rain_intensity"]

            base_water = field.get(
                'base_today_water', field.get(
                    'today_water', 0))
            base_time = field.get(
                'base_time_needed', field.get(
                    'time_needed', 0))

            new_status = field.get('status')
            new_progress = field.get('progress')
            new_water = base_water
            new_time = base_time

            if rain_intensity > RAIN_THRESHOLD_MMH:
                new_status = "hydrated"
                new_progress = 100
                new_water = 0
                new_time = 0
            elif avg_moisture < MOISTURE_MIN_THRESHOLD:
                new_status = "dehydrated"
                new_progress = 0
                new_water = base_water
                new_time = base_time
            elif avg_moisture > MOISTURE_MAX_THRESHOLD:
                new_status = "hydrated"
                new_progress = 100
                new_water = 0
                new_time = 0
            else:
                new_status = "hydrated"
                new_progress = int(
                    (avg_moisture / MOISTURE_MAX_THRESHOLD) * 100)
                new_progress = max(0, min(100, new_progress))

                remaining_factor = 1.0 - (new_progress / 100.0)
                new_water = round(base_water * remaining_factor, 1)
                new_time = round(base_time * remaining_factor, 1)

            update_data = {
                "status": new_status,
                "progress": new_progress,
                "today_water": new_water,
                "time_needed": new_time,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }

            try:
                db.update("fields", {"id": field.get('id')}, update_data)
                updated_count += 1
            except Exception as e:
                logger.error(f"Lỗi khi cập nhật vườn {field.get('id')}: {e}")

    return updated_count


@st.dialog("✏️ Chỉnh sửa thông tin Vườn")
def render_edit_modal(field, all_crops):
    with st.form("edit_field_form"):
        st.info(f"Bạn đang chỉnh sửa: **{field.get('name')}**")

        current_name = field.get('name', '')
        current_crop = field.get('crop', 'Lúa')
        current_stage = field.get('stage', 'Ươm')
        current_status = field.get('status', 'hydrated')
        current_progress = field.get('progress', 0)

        new_name = st.text_input("Tên Vườn", value=current_name)

        col1, col2 = st.columns(2)
        with col1:
            CROP_OPTIONS = all_crops
            try:
                crop_index = CROP_OPTIONS.index(current_crop)
            except ValueError:
                CROP_OPTIONS.append(current_crop)
                crop_index = CROP_OPTIONS.index(current_crop)
            new_crop = st.selectbox(
                "Loại Cây Trồng",
                options=CROP_OPTIONS,
                index=crop_index)

            STATUS_OPTIONS = ['hydrated', 'dehydrated', 'severely_dehydrated']
            try:
                status_index = STATUS_OPTIONS.index(current_status)
            except ValueError:
                status_index = 0
            new_status = st.selectbox(
                "Trạng thái tưới",
                options=STATUS_OPTIONS,
                index=status_index,
                help="Ghi đè thủ công trạng thái tưới.")
        with col2:
            STAGE_OPTIONS = [
                "Ươm",
                "Phát triển",
                "Ra hoa",
                "Ra quả",
                "Trưởng thành"]
            try:
                stage_index = STAGE_OPTIONS.index(current_stage)
            except ValueError:
                stage_index = 0
            new_stage = st.selectbox(
                "Giai Đoạn",
                options=STAGE_OPTIONS,
                index=stage_index)

            new_progress = st.slider("Ghi đè Tiến độ tưới (%)", 0, 100, int(
                current_progress), help="Ghi đè thủ công tiến độ tưới của vườn.")

        st.markdown("---")

        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.form_submit_button(
                "💾 Lưu thay đổi",
                type="primary",
                    use_container_width=True):
                base_water = field.get(
                    'base_today_water', field.get(
                        'today_water', 0))
                base_time = field.get(
                    'base_time_needed', field.get(
                        'time_needed', 0))

                remaining_factor = 1.0 - (new_progress / 100.0)
                recalculated_water = round(base_water * remaining_factor, 1)
                recalculated_time = round(base_time * remaining_factor, 1)

                update_data = {
                    "name": new_name,
                    "crop": new_crop,
                    "stage": new_stage,
                    "status": new_status,
                    "progress": new_progress,
                    "today_water": recalculated_water,
                    "time_needed": recalculated_time,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }

                try:
                    if db.update(
                        "fields", {
                            "id": field.get('id')}, update_data):
                        st.success("Cập nhật vườn thành công!")
                        st.session_state.editing_field = None
                        get_field_data.clear()
                        st.rerun()
                    else:
                        st.error("Lỗi: Không thể cập nhật vườn trong DB.")
                except Exception as e:
                    st.error(f"Lỗi khi lưu: {e}")

        with col_cancel:
            if st.form_submit_button("Hủy", use_container_width=True):
                st.session_state.editing_field = None
                st.rerun()


def render_fields():
    if not (hasattr(st, 'user') and st.user.email):
        st.error("Vui lòng đăng nhập để xem các vườn")
        return

    fields, hydration_jobs = get_field_data(st.user.email)
    all_crops = get_available_crops()

    st.session_state.fields = fields

    with st.container(border=True):
        st.markdown("### 💧 Tiến độ tưới")
        st.markdown("Cùng theo dõi tiến độ tưới nước hôm nay nhé:")
        box_css = """
            <div style="border: 2px solid {color}; border-radius: 10px; padding: 12px; text-align: center; margin-bottom: 10px;">
                <h4 style="margin: 0; color: {color};">{label}</h4>
                <p style="font-size: 24px; font-weight: bold; margin: 5px 0;">{value}</p>
            </div>
        """
        cols = st.columns(3)
        with cols[0]:
            st.markdown(
                box_css.format(
                    label="✅ Hoàn thành",
                    value=hydration_jobs['completed'],
                    color="#2e7d32"),
                unsafe_allow_html=True)
        with cols[1]:
            st.markdown(
                box_css.format(
                    label="🚿 Đang hoạt động",
                    value=hydration_jobs['active'],
                    color="#0277bd"),
                unsafe_allow_html=True)
        with cols[2]:
            st.markdown(
                box_css.format(
                    label="⏳ Chờ xử lý",
                    value=hydration_jobs['remaining'],
                    color="#f57c00"),
                unsafe_allow_html=True)

    col_title, col_add, col_update = st.columns([3, 1, 2])
    with col_title:
        st.subheader("Tất cả các vườn")
    with col_add:
        if st.button("➕ Thêm vườn", type="primary", use_container_width=True):
            st.session_state.navigate_to = "Add Field"
            st.rerun()
    with col_update:
        if st.button(
            "🔄 Cập nhật Trạng thái (Lưu vào DB)",
                use_container_width=True):
            with st.spinner("Đang tính toán và cập nhật trạng thái từ cảm biến..."):
                num_updated = run_field_update(st.user.email)
                get_field_data.clear()
                st.success(f"Đã cập nhật {num_updated} vườn.")
                st.rerun()

    if fields:
        st.info(f"📊 Bạn có {len(fields)} vườn")
    else:
        st.info("🌱 Bạn chưa có vườn nào. Hãy thêm vườn đầu tiên!")
        st.markdown("👉 **Nhấn nút 'Thêm vườn' ở trên để tạo vườn mới**")
        return

    search_query = st.text_input("",
                                 placeholder="Tìm kiếm vườn",
                                 label_visibility="collapsed")

    if "editing_field" in st.session_state and st.session_state.editing_field:
        field_to_edit = st.session_state.editing_field
        render_edit_modal(field_to_edit, all_crops)

    if search_query:
        filtered_fields = [
            f for f in fields if search_query.lower() in f.get(
                'name', '').lower() or search_query.lower() in f.get(
                'crop', '').lower()]
    else:
        filtered_fields = fields

    if not filtered_fields:
        st.warning(f"Không tìm thấy vườn nào với từ khóa '{search_query}'")
        return

    for field in filtered_fields:
        live_stats = get_latest_telemetry_stats(st.user.email, field.get('id'))

        display_status = field.get("status", "hydrated")
        display_water = field.get('today_water', 0)
        display_time = field.get('time_needed', 0)
        
        # Ưu tiên lấy progress từ DB
        if field.get("progress") is not None:
            display_progress = field.get("progress")
        else:
            display_progress = 0

        caption_text = "(Dữ liệu đã lưu)"

        # Chỉ tính toán lại nều không có progress trong DB HOẶC muốn cập nhật các thông số khác theo thời gian thực
        # Tuy nhiên yêu cầu là ưu tiên DB cho progress.
        # Logic cũ đã ghi đè display_progress bằng tính toán live.
        # Sửa lại: Chỉ tính toán live nếu field chưa có progress (None)
        
        if live_stats and live_stats.get("avg_moisture") is not None:
            avg_moisture = live_stats["avg_moisture"]
            rain_intensity = live_stats["rain_intensity"]
            
            # Nếu DB chưa có progress, tính toán live
            if field.get("progress") is None:
                base_water = field.get('base_today_water', display_water)
                base_time = field.get('base_time_needed', display_time)

                if rain_intensity > RAIN_THRESHOLD_MMH:
                    display_status = "hydrated"
                    display_progress = 100
                    display_water = 0
                    display_time = 0
                elif avg_moisture < MOISTURE_MIN_THRESHOLD:
                    display_status = "dehydrated"
                    display_progress = 0
                    display_water = base_water
                    display_time = base_time
                elif avg_moisture > MOISTURE_MAX_THRESHOLD:
                    display_status = "hydrated"
                    display_progress = 100
                    display_water = 0
                    display_time = 0
                else:
                    display_status = "hydrated"
                    progress_range = MOISTURE_MAX_THRESHOLD - MOISTURE_MIN_THRESHOLD
                    current_progress = avg_moisture - MOISTURE_MIN_THRESHOLD
                    display_progress = int(
                        (current_progress / progress_range) * 100)

                    remaining_factor = 1.0 - (display_progress / 100.0)
                    display_water = round(base_water * remaining_factor, 1)
                    display_time = round(base_time * remaining_factor, 1)

            try:
                ts = datetime.fromisoformat(
                    live_stats['timestamp']).strftime("%H:%M:%S")
                caption_text = f"(Live: {avg_moisture:.1f}% @ {ts})"
            except BaseException:
                caption_text = f"(Live: {avg_moisture:.1f}%)"
        
        # Force progress limits
        display_progress = max(0, min(100, display_progress))

        status_colors = {
            'hydrated': {
                'bg': '#d4edda',
                'text': '#155724',
                'overlay': 'green'},
            'dehydrated': {
                'bg': '#fff3cd',
                'text': '#856404',
                'overlay': 'orange'},
            'severely_dehydrated': {
                'bg': '#f8d7da',
                'text': '#721c24',
                'overlay': 'red'}}
        color_info = status_colors.get(
            display_status, status_colors['hydrated'])

        with st.container(border=True):
            cols = st.columns([2, 5, 2, 2])

            with cols[0]:
                if 'polygon' in field and field['polygon']:
                    m = folium.Map(
                        location=field.get(
                            'center',
                            [
                                20.45,
                                106.32]),
                        zoom_start=16,
                        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                        attr="EWI")
                    folium.Polygon(
                        locations=field['polygon'],
                        color=color_info['overlay'],
                        fill=True,
                        fill_color=color_info['overlay'],
                        fill_opacity=0.5,
                        weight=2).add_to(m)
                    st_folium(
                        m,
                        width=200,
                        height=150,
                        returned_objects=[],
                        key=f"map_{
                            field.get(
                                'id',
                                'unknown')}")
                else:
                    st.image(
                        "https://upload.wikimedia.org/wikipedia/commons/6/65/No-Image-Placeholder.svg",
                        caption="Không có bản đồ")

            with cols[1]:
                st.markdown(
                    f"**{field.get('name', 'Vườn không tên')}**  {field.get('area', 0):.2f} ha")

                status_badge = f'<span style="background-color: {
                    color_info["bg"]}; color: {
                    color_info["text"]}; padding: 6px 12px; border-radius: 20px; font-weight: bold;">Trạng thái tưới  {
                    display_status.title().replace(
                        "_", " ")}</span>'
                st.markdown(status_badge, unsafe_allow_html=True)

                st.markdown(
                    f"Nước tưới hôm nay  {display_water} m³ {caption_text}")
                st.markdown(
                    f"Cây trồng: {
                        field.get(
                            'crop',
                            'Không xác định')} | Giai đoạn: {
                        field.get(
                            'stage',
                            'Không xác định')}")

            with cols[2]:
                st.markdown(
                    '<p style="text-align: right; color: #6c757d; font-size: 12px;">THỜI GIAN CẦN</p>',
                    unsafe_allow_html=True)
                st.markdown(
                    f'<p style="text-align: right; font-size: 18px; font-weight: bold;">{display_time} giờ</p>',
                    unsafe_allow_html=True)

            with cols[3]:
                st.markdown(
                    '<p style="text-align: right; color: #6c757d; font-size: 12px;">TRẠNG THÁI</p>',
                    unsafe_allow_html=True)
                st.markdown(
                    render_progress(display_progress),
                    unsafe_allow_html=True)

                col_edit, col_delete = st.columns(2)
                with col_edit:
                    if st.button(
                        "✏️",
                        key=f"edit_{
                            field.get(
                                'id',
                                'unknown')}",
                            help="Chỉnh sửa vườn"):
                        st.session_state.editing_field = field
                        st.rerun()

                with col_delete:
                    if st.button(
                        "🗑️",
                        key=f"delete_{
                            field.get(
                                'id',
                                'unknown')}",
                            help="Xóa vườn"):
                        try:
                            if db.delete("fields", {"id": field.get('id')}):
                                st.success("Xóa vườn thành công!")
                                get_field_data.clear()
                                st.rerun()
                            else:
                                st.error("Lỗi: Không thể xóa vườn.")
                        except Exception as e:
                            st.error(f"Lỗi khi xóa: {e}")
