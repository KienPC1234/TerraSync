# pages/my_fields.py
import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
from database import db
from datetime import datetime, timezone
import logging
# Import CROP_DATABASE từ add_field.py
from .add_field import CROP_DATABASE 

# Cấu hình logging
logger = logging.getLogger("my_fields_app")

# --- Hằng số cho logic tưới tiêu (có thể chỉnh) ---
MOISTURE_MIN_THRESHOLD = 25.0  # Dưới mức này là 'dehydrated'
MOISTURE_MAX_THRESHOLD = 75.0  # Trên mức này là 'hydrated'
RAIN_THRESHOLD_MMH = 1.0       # Mưa (mm/h) để coi là đang tưới

# ========================================
# HELPER: Vòng tròn tiến độ (Giữ nguyên)
# ========================================
def render_progress(value):
    """Hiển thị vòng tròn tiến độ"""
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

# ========================================
# HELPER: Tải dữ liệu Field (Giữ nguyên)
# ========================================
@st.cache_data(ttl=60)
def get_field_data(user_email: str):
    """Tải và phân tích dữ liệu fields từ DB."""
    
    user_fields = db.get("fields", {"user_email": user_email})
    fields = user_fields if user_fields else []
    
    hydration_jobs = {
        'completed': 0,
        'active': 0,
        'remaining': 0
    }
    
    for f in fields:
        progress = f.get('progress', 0)
        if progress == 100:
            hydration_jobs['completed'] += 1
        elif 0 < progress < 100:
            hydration_jobs['active'] += 1
        else: 
            hydration_jobs['remaining'] += 1
            
    return fields, hydration_jobs

# ========================================
# HELPERS: Dữ liệu cây trồng (Giữ nguyên)
# ========================================
def get_crop_characteristics(crop_name: str):
    """Lấy thông số mặc định của cây trồng."""
    if crop_name in CROP_DATABASE:
        return CROP_DATABASE[crop_name]
    return {
        "crop_coefficient": 1.0,
        "irrigation_efficiency": 85,
    }

def get_available_crops(user_email: str) -> list[str]:
    """Lấy danh sách các loại cây trồng user đã dùng + cây trồng mặc định."""
    try:
        user_crops = db.get("crops", {"user_email": user_email}) or []
        names = [c.get("name") for c in user_crops if c.get("name")]
        allc = list(CROP_DATABASE.keys())
        for n in names:
            if n not in allc:
                allc.append(n)
        return sorted(list(set(allc)))
    except Exception:
        return sorted(list(CROP_DATABASE.keys()))

# ========================================
# HELPERS: Lấy dữ liệu Telemetry (MỚI)
# (Sao chép từ my_schedule.py để tránh lỗi circular import)
# ========================================
def get_hub_id_for_field(user_email: str, field_id: str) -> str | None:
    """Helper: Lấy hub_id được gán cho field."""
    hub = db.get("iot_hubs", {"field_id": field_id, "user_email": user_email})
    if hub:
        return hub[0].get('hub_id')
    return None

def get_latest_telemetry_stats(user_email: str, field_id: str) -> dict | None:
    """
    Lấy GÓI TIN telemetry MỚI NHẤT (không cache) để tính toán.
    """
    hub_id = get_hub_id_for_field(user_email, field_id)
    if not hub_id:
        # logger.warning(f"Không tìm thấy hub cho field {field_id}")
        return None 

    telemetry_data = db.get("telemetry", {"hub_id": hub_id})
    if not telemetry_data:
        # logger.warning(f"Không tìm thấy telemetry cho hub {hub_id}")
        return None
    
    try:
        latest_entry = sorted(
            telemetry_data, 
            key=lambda x: x.get('timestamp', '1970-01-01T00:00:00+00:00'), 
            reverse=True
        )[0]
    except IndexError:
        return None
        
    data = latest_entry.get("data", {})
    stats = {
        "avg_moisture": None,
        "rain_intensity": 0.0,
        "timestamp": latest_entry.get('timestamp')
    }

    nodes = data.get("soil_nodes", [])
    if nodes:
        values = [n['sensors']['soil_moisture'] for n in nodes if n.get('sensors') and 'soil_moisture' in n['sensors']]
        if values:
            stats["avg_moisture"] = sum(values) / len(values)

    atm_node = data.get("atmospheric_node", {})
    if atm_node.get('sensors') and 'rain_intensity' in atm_node['sensors']:
        stats["rain_intensity"] = atm_node['sensors']['rain_intensity']
        
    return stats

# ========================================
# HÀM MỚI: Cập nhật trạng thái
# ========================================
def run_field_update(user_email: str):
    """
    Chạy tính toán động cho TẤT CẢ các field và LƯU vào DB.
    """
    fields = db.get("fields", {"user_email": user_email})
    if not fields:
        return 0
    
    updated_count = 0
    for field in fields:
        live_stats = get_latest_telemetry_stats(user_email, field.get('id'))
        
        # Chỉ cập nhật nếu có dữ liệu cảm biến
        if live_stats and live_stats.get("avg_moisture") is not None:
            avg_moisture = live_stats["avg_moisture"]
            rain_intensity = live_stats["rain_intensity"]
            
            # Lấy mục tiêu từ DB
            db_today_water = field.get('today_water', 0)
            db_time_needed = field.get('time_needed', 0)
            
            new_status = field.get('status')
            new_progress = field.get('progress')
            new_water = db_today_water
            new_time = db_time_needed

            if rain_intensity > RAIN_THRESHOLD_MMH:
                new_status = "hydrated"
                new_progress = 100
                new_water = 0
                new_time = 0
            elif avg_moisture < MOISTURE_MIN_THRESHOLD:
                new_status = "dehydrated"
                new_progress = 0
                new_water = db_today_water # Cần tưới
                new_time = db_time_needed
            elif avg_moisture > MOISTURE_MAX_THRESHOLD:
                new_status = "hydrated"
                new_progress = 100
                new_water = 0
                new_time = 0
            else: # Trong ngưỡng
                new_status = "hydrated"
                progress_range = MOISTURE_MAX_THRESHOLD - MOISTURE_MIN_THRESHOLD
                current_progress = avg_moisture - MOISTURE_MIN_THRESHOLD
                new_progress = int((current_progress / progress_range) * 100)
                
                remaining_factor = 1.0 - (new_progress / 100.0)
                new_water = round(db_today_water * remaining_factor, 1)
                new_time = round(db_time_needed * remaining_factor, 1)

            # Cập nhật nếu có thay đổi
            update_data = {
                "status": new_status,
                "progress": new_progress,
                "today_water": new_water,
                "time_needed": new_time,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            try:
                db.update_user_field(field.get('id'), user_email, update_data)
                updated_count += 1
            except Exception as e:
                logger.error(f"Lỗi khi cập nhật field {field.get('id')}: {e}")
                
    return updated_count

# ========================================
# HÀM EDIT MODAL (ĐÃ SỬA LỖI)
# ========================================
# SỬA LỖI: Dùng @st.dialog làm decorator
@st.dialog("✏️ Chỉnh sửa thông tin Vườn")
def render_edit_modal(field, all_crops):
    """Hiển thị dialog (cửa sổ) để chỉnh sửa thông tin field."""
    
    with st.form("edit_field_form"):
        st.info(f"Bạn đang chỉnh sửa: **{field.get('name')}**")
        
        current_name = field.get('name', '')
        current_crop = field.get('crop', 'Rice')
        current_stage = field.get('stage', 'Seedling')
        current_status = field.get('status', 'hydrated')

        CROP_OPTIONS = all_crops
        STAGE_OPTIONS = ["Seedling", "Vegetative", "Flowering", "Fruiting", "Maturity"]
        STATUS_OPTIONS = ['hydrated', 'dehydrated', 'severely_dehydrated']

        try:
            crop_index = CROP_OPTIONS.index(current_crop)
        except ValueError:
            CROP_OPTIONS.append(current_crop) 
            crop_index = CROP_OPTIONS.index(current_crop)
        
        try:
            stage_index = STAGE_OPTIONS.index(current_stage)
        except ValueError:
            stage_index = 0 

        try:
            status_index = STATUS_OPTIONS.index(current_status)
        except ValueError:
            status_index = 0

        new_name = st.text_input("Tên Vườn (Field Name)", value=current_name)
        new_crop = st.selectbox("Loại Cây Trồng (Crop Type)", options=CROP_OPTIONS, index=crop_index)
        new_stage = st.selectbox("Giai Đoạn (Growth Stage)", options=STAGE_OPTIONS, index=stage_index)
        new_status = st.selectbox("Trạng thái tưới (Hydration Status)", options=STATUS_OPTIONS, index=status_index,
                                    help="Ghi đè thủ công trạng thái tưới.")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💾 Lưu thay đổi", type="primary", use_container_width=True):
                update_data = {
                    "name": new_name,
                    "crop": new_crop,
                    "stage": new_stage,
                    "status": new_status, # Lưu trạng thái do user chọn
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
                
                try:
                    if db.update_user_field(field.get('id'), field.get('user_email'), update_data):
                        st.success("Cập nhật vườn thành công!")
                        st.session_state.editing_field = None
                        get_field_data.clear() 
                        st.rerun()
                    else:
                        st.error("Lỗi: Không thể cập nhật vườn trong DB.")
                except AttributeError:
                    st.error("Lỗi Lập trình: Hàm 'db.update_user_field' không tồn tại.")
                except Exception as e:
                    st.error(f"Lỗi khi lưu: {e}")

        with col2:
            if st.form_submit_button("Hủy", use_container_width=True):
                st.session_state.editing_field = None
                st.rerun()

# ========================================
# HÀM RENDER CHÍNH (Đã sửa)
# ========================================
def render_fields():
    
    if not (hasattr(st, 'user') and st.user.email):
        st.error("Vui lòng đăng nhập để xem fields")
        return
    
    # Tải dữ liệu
    fields, hydration_jobs = get_field_data(st.user.email)
    all_crops = get_available_crops(st.user.email) 
    
    st.session_state.fields = fields
    
    # Header Cards (Sử dụng dữ liệu động từ get_field_data)
    with st.container(border=True):
        st.markdown("### 💧 Hydration Jobs")
        st.markdown("Cùng theo dõi tiến độ tưới nước hôm nay nhé:")
        box_css = """
            <div style="border: 2px solid {color}; border-radius: 10px; padding: 12px; text-align: center; margin-bottom: 10px;">
                <h4 style="margin: 0; color: {color};">{label}</h4>
                <p style="font-size: 24px; font-weight: bold; margin: 5px 0;">{value}</p>
            </div>
        """
        cols = st.columns(3)
        with cols[0]:
            st.markdown(box_css.format(label="✅ Completed", value=hydration_jobs['completed'], color="#2e7d32"), unsafe_allow_html=True)
        with cols[1]:
            st.markdown(box_css.format(label="🚿 Active", value=hydration_jobs['active'], color="#0277bd"), unsafe_allow_html=True)
        with cols[2]:
            st.markdown(box_css.format(label="⏳ Remaining", value=hydration_jobs['remaining'], color="#f57c00"), unsafe_allow_html=True)

    
    # All Fields
    col_title, col_add, col_update = st.columns([3, 1, 2])
    with col_title:
        st.subheader("All Fields")
    with col_add:
        if st.button("➕ Add Field", type="primary", use_container_width=True):
            st.session_state.navigate_to = "Add Field"
            st.rerun()
    with col_update:
        # NÚT CẬP NHẬT MỚI
        if st.button("🔄 Cập nhật Trạng thái (Lưu vào DB)", use_container_width=True):
            with st.spinner("Đang tính toán và cập nhật trạng thái từ cảm biến..."):
                num_updated = run_field_update(st.user.email)
                get_field_data.clear()
                st.success(f"Đã cập nhật {num_updated} vườn.")
                st.rerun()

    
    if fields:
        st.info(f"📊 Bạn có {len(fields)} field(s)")
    else:
        st.info("🌱 Bạn chưa có field nào. Hãy thêm field đầu tiên!")
        st.markdown("👉 **Click nút 'Add Field' ở trên để tạo field mới**")
        return
    
    search_query = st.text_input("", placeholder="Search fields", label_visibility="collapsed")
    
    # Kích hoạt Dialog Edit
    if "editing_field" in st.session_state and st.session_state.editing_field:
        field_to_edit = st.session_state.editing_field
        render_edit_modal(field_to_edit, all_crops)
        
    if search_query:
        filtered_fields = [f for f in fields if search_query.lower() in f.get('name', '').lower() or search_query.lower() in f.get('crop', '').lower()]
    else:
        filtered_fields = fields
    
    if not filtered_fields:
        st.warning(f"Không tìm thấy field nào với từ khóa '{search_query}'")
        return
    
    # --- Vòng lặp hiển thị danh sách (ĐÃ SỬA) ---
    for field in filtered_fields:
        
        # --- TÍNH TOÁN ĐỘNG CHO HIỂN THỊ ---
        live_stats = get_latest_telemetry_stats(st.user.email, field.get('id'))
        
        # Lấy giá trị DB làm mặc định
        display_status = field.get("status", "hydrated")
        display_water = field.get('today_water', 0)
        display_time = field.get('time_needed', 0)
        display_progress = field.get('progress', 0)
        
        caption_text = "(Dữ liệu đã lưu)"

        if live_stats and live_stats.get("avg_moisture") is not None:
            avg_moisture = live_stats["avg_moisture"]
            rain_intensity = live_stats["rain_intensity"]
            db_today_water = field.get('today_water', 0)
            db_time_needed = field.get('time_needed', 0)
            
            if rain_intensity > RAIN_THRESHOLD_MMH:
                display_status = "hydrated"
                display_progress = 100
                display_water = 0
                display_time = 0
            elif avg_moisture < MOISTURE_MIN_THRESHOLD:
                display_status = "dehydrated"
                display_progress = 0
                display_water = db_today_water
                display_time = db_time_needed
            elif avg_moisture > MOISTURE_MAX_THRESHOLD:
                display_status = "hydrated"
                display_progress = 100
                display_water = 0
                display_time = 0
            else: # Trong ngưỡng
                display_status = "hydrated"
                progress_range = MOISTURE_MAX_THRESHOLD - MOISTURE_MIN_THRESHOLD
                current_progress = avg_moisture - MOISTURE_MIN_THRESHOLD
                display_progress = int((current_progress / progress_range) * 100)
                
                remaining_factor = 1.0 - (display_progress / 100.0)
                display_water = round(db_today_water * remaining_factor, 1)
                display_time = round(db_time_needed * remaining_factor, 1)
            
            try:
                ts = datetime.fromisoformat(live_stats['timestamp']).strftime("%H:%M:%S")
                caption_text = f"(Live: {avg_moisture:.1f}% @ {ts})"
            except:
                caption_text = f"(Live: {avg_moisture:.1f}%)"
        
        # --- Kết thúc tính toán động ---
        
        status_colors = {
            'hydrated': {'bg': '#d4edda', 'text': '#155724', 'overlay': 'green'},
            'dehydrated': {'bg': '#fff3cd', 'text': '#856404', 'overlay': 'orange'},
            'severely_dehydrated': {'bg': '#f8d7da', 'text': '#721c24', 'overlay': 'red'}
        }
        # Dùng display_status để chọn màu
        color_info = status_colors.get(display_status, status_colors['hydrated'])
        
        with st.container(border=True):
            cols = st.columns([2, 5, 2, 2])
            
            with cols[0]:
                if 'polygon' in field and field['polygon']:
                    m = folium.Map(location=field.get('center', [20.45, 106.32]), zoom_start=16, 
                                   tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="EWI")
                    folium.Polygon(locations=field['polygon'], color=color_info['overlay'], fill=True,
                                   fill_color=color_info['overlay'], fill_opacity=0.5, weight=2).add_to(m)
                    st_folium(m, width=200, height=150, returned_objects=[], key=f"map_{field.get('id', 'unknown')}")
                else:
                    st.image("https.upload.wikimedia.org/wikipedia/commons/6/65/No-Image-Placeholder.svg", caption="No map available")
            
            with cols[1]:
                st.markdown(f"**{field.get('name', 'Unnamed Field')}**  {field.get('area', 0):.2f} ha")
                
                # Dùng display_status cho badge
                status_badge = f'<span style="background-color: {color_info["bg"]}; color: {color_info["text"]}; padding: 6px 12px; border-radius: 20px; font-weight: bold;">Crop Hydration  {display_status.title().replace("_", " ")}</span>'
                st.markdown(status_badge, unsafe_allow_html=True)
                
                # Dùng display_water
                st.markdown(f"Today's Water  {display_water} m³ {caption_text}")
                st.markdown(f"Crop: {field.get('crop', 'Unknown')} | Stage: {field.get('stage', 'Unknown')}")
            
            with cols[2]:
                st.markdown('<p style="text-align: right; color: #6c757d; font-size: 12px;">TIME NEEDED</p>', unsafe_allow_html=True)
                # Dùng display_time
                st.markdown(f'<p style="text-align: right; font-size: 18px; font-weight: bold;">{display_time} hours</p>', unsafe_allow_html=True)
            
            with cols[3]:
                st.markdown('<p style="text-align: right; color: #6c757d; font-size: 12px;">STATUS</p>', unsafe_allow_html=True)
                # Dùng display_progress
                st.markdown(render_progress(display_progress), unsafe_allow_html=True)
                
                col_edit, col_delete = st.columns(2)
                with col_edit:
                    if st.button("✏️", key=f"edit_{field.get('id', 'unknown')}", help="Edit field"):
                        st.session_state.editing_field = field
                        st.rerun() 
                
                with col_delete:
                    if st.button("🗑️", key=f"delete_{field.get('id', 'unknown')}", help="Delete field"):
                        try:
                            if db.delete_user_field(field.get('id', ''), st.user.email): 
                                st.success("Xóa vườn thành công!")
                                get_field_data.clear()
                                st.rerun()
                            else:
                                st.error("Lỗi: Không thể xóa vườn.")
                        except Exception as e:
                            st.error(f"Lỗi khi xóa: {e}")