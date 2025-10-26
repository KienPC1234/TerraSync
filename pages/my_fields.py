import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
from database import db
from utils import get_default_fields

def render_progress(value):
    color = "#28a745" if value >= 80 else "#ffc107" if value >= 30 else "#dc3545"
    html = f"""
    <div style="position: relative; width: 60px; height: 60px; margin: auto;">
        <svg viewBox="0 0 36 36" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; transform: rotate(-90deg);">
            <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#e9ecef" stroke-width="3" />
            <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="{color}" stroke-width="3" stroke-dasharray="{value * 100 / 100}, 100" stroke-linecap="round" />
        </svg>
        <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 12px; font-weight: bold; color: #495057; text-align: center;">{value}%<br><span style="font-size: 10px; font-weight: normal;">Progress</span></div>
    </div>
    """
    return html

def render_fields():
    st.set_page_config(page_title="My Fields", page_icon="🌱", layout="wide")
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .metric-container {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .field-card {
        background: white;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s ease-in-out;
    }
    .field-card:hover {
        transform: translateY(-2px);
    }
    .status-badge {
        padding: 8px 16px;
        border-radius: 25px;
        font-weight: bold;
        font-size: 12px;
        display: inline-block;
    }
    .action-btn {
        border: none;
        background: none;
        font-size: 16px;
        padding: 8px;
        border-radius: 50%;
        cursor: pointer;
        transition: background 0.2s;
    }
    .action-btn:hover {
        background: #f0f0f0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Check if user is logged in
    if not hasattr(st, 'user') or not st.user.is_logged_in:
        st.error("❌ Vui lòng đăng nhập để xem fields")
        return
    
    # Lấy fields từ database
    user_fields = db.get_user_fields(st.user.email)
    fields = user_fields if user_fields else []
    
    # Cập nhật session state
    st.session_state.fields = fields
    
    if "hydration_jobs" not in st.session_state:
        st.session_state.hydration_jobs = {'completed': 2, 'active': 1, 'remaining': 3}
    
    # Header with Hydration Jobs - Enhanced with gradient cards
    
    st.markdown("# 🌾 My Fields Dashboard")
    st.markdown("### 💧 Hydration Jobs Today")
    st.markdown("Theo dõi tiến độ tưới nước hôm nay một cách trực quan!")

    box_css = """
    <div class="metric-container" style="border-left: 5px solid {color};">
        <h4 style="margin: 0 0 8px 0; color: {color}; font-size: 14px;">{icon} {label}</h4>
        <p style="font-size: 28px; font-weight: bold; margin: 0; color: #333;">{value}</p>
    </div>
    """

    cols = st.columns(3)
    with cols[0]:
        st.markdown(box_css.format(
            label="Completed",
            value=st.session_state.hydration_jobs['completed'],
            color="#28a745",
            icon="✅"
        ), unsafe_allow_html=True)

    with cols[1]:
        st.markdown(box_css.format(
            label="Active",
            value=st.session_state.hydration_jobs['active'],
            color="#007bff",
            icon="🚿"
        ), unsafe_allow_html=True)

    with cols[2]:
        st.markdown(box_css.format(
            label="Remaining",
            value=st.session_state.hydration_jobs['remaining'],
            color="#fd7e14",
            icon="⏳"
        ), unsafe_allow_html=True)
    
        st.markdown("### 🌱 All Your Fields")
        
    
    # Show field count with icon
    if fields:
        st.success(f"📊 Bạn đang quản lý **{len(fields)} field(s)**")
    else:
        st.warning("🌱 Bạn chưa có field nào.")
        st.markdown("👉 **Nhấp vào nút 'Add New Field' ở trên để bắt đầu!**")
        col_img, col_text = st.columns([1, 3])
        with col_img:
            st.image("https://img.freepik.com/free-vector/hand-drawn-flat-design-plantation-illustration_23-2148990153.jpg", use_container_width=True)
        with col_text:
            st.markdown("""
            ### Bắt đầu hành trình nông nghiệp của bạn
            - Thêm field đầu tiên bằng cách nhập tọa độ và vẽ ranh giới.
            - Sử dụng AI để phát hiện tự động hoặc vẽ thủ công.
            - Theo dõi sức khỏe cây trồng và lịch tưới nước.
            """)
        return
    
    # Search with better placeholder
    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        search_query = st.text_input("🔍 Tìm kiếm theo tên field hoặc loại cây...", placeholder="Nhập từ khóa tìm kiếm", label_visibility="collapsed")
    with search_col2:
        if st.button("🔄 Refresh", type="secondary", use_container_width=True):
            st.rerun()
    
    # Filter fields based on search
    if search_query:
        filtered_fields = [f for f in fields if search_query.lower() in f.get('name', '').lower() or search_query.lower() in f.get('crop', '').lower()]
    else:
        filtered_fields = fields
    
    if not filtered_fields:
        st.warning(f"❌ Không tìm thấy field nào với từ khóa '{search_query}'")
        st.info("💡 Thử tìm kiếm bằng tên field hoặc loại cây trồng.")
        return
    
    # Display fields in a grid-like layout
    
    for i, field in enumerate(filtered_fields):
        status_colors = {
            'hydrated': {'bg': '#d4edda', 'text': '#155724', 'overlay': '#28a745'},
            'dehydrated': {'bg': '#fff3cd', 'text': '#856404', 'overlay': '#ffc107'},
            'severely_dehydrated': {'bg': '#f8d7da', 'text': '#721c24', 'overlay': '#dc3545'}
        }
        color_info = status_colors.get(field.get('status', 'hydrated'), status_colors['hydrated'])
        
        with st.container(border=True, key=f"field_card_{field.get('id', i)}"):
            st.markdown(f'<div class="field-card">', unsafe_allow_html=True)
            cols = st.columns([1.5, 4, 1.5, 1.5])
            
            with cols[0]:
                st.markdown("### 🗺️ Bản đồ")
                # Enhanced map preview with better sizing
                if 'polygon' in field and field['polygon']:
                    m = folium.Map(
                        location=[field.get('center', [field.get('lat', 20.45), field.get('lon', 106.32)])[0], 
                                 field.get('center', [field.get('lat', 20.45), field.get('lon', 106.32)])[1]], 
                        zoom_start=16, 
                        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                        attr="Esri World Imagery"
                    )
                    folium.Polygon(
                        locations=field['polygon'],
                        color=color_info['overlay'],
                        fill=True,
                        fillColor=color_info['overlay'],
                        fillOpacity=0.4,
                        weight=3,
                        popup=folium.Popup(f"{field.get('name')} - {field.get('area', 0):.2f} ha", parse_html=True)
                    ).add_to(m)
                    st_folium(m, width=250, height=180, returned_objects=[], key=f"map_{field.get('id', i)}")
                else:
                    st.markdown("![No Map](https://via.placeholder.com/250x180/eee/ccc?text=No+Map+Available)")
            
            with cols[1]:
                st.markdown(f"### **{field.get('name', 'Unnamed Field')}**")
                st.markdown(f"🌾 **Diện tích:** {field.get('area', 0):.2f} ha")
                
                status_badge = f'<span class="status-badge" style="background-color: {color_info["bg"]}; color: {color_info["text"]};">💧 {field.get("status", "hydrated").title().replace("_", " ")}</span>'
                st.markdown(status_badge, unsafe_allow_html=True)
                
                col_details1, col_details2 = st.columns(2)
                with col_details1:
                    st.markdown(f"**Cây trồng:** {field.get('crop', 'Unknown')}")
                with col_details2:
                    st.markdown(f"**Giai đoạn:** {field.get('stage', 'Unknown')}")
                
                st.markdown(f"💦 **Nước hôm nay:** {field.get('today_water', 0):,.0f} lít")
            
            with cols[2]:
                st.markdown("### ⏱️ Thời gian cần")
                st.markdown(f"<div style='text-align: center; font-size: 24px; font-weight: bold; color: #495057;'>{field.get('time_needed', 0)}h</div>", unsafe_allow_html=True)
                st.markdown("<div style='text-align: center; font-size: 12px; color: #6c757d;'>Irrigation</div>", unsafe_allow_html=True)
            
            with cols[3]:
                st.markdown("### 📈 Tiến độ")
                st.markdown(render_progress(field.get('progress', 0)), unsafe_allow_html=True)
                st.markdown(f"<div style='text-align: center; font-size: 12px; color: #6c757d;'>{field.get('days_to_harvest', 0)} ngày đến thu hoạch</div>", unsafe_allow_html=True)
                
                # Action buttons in a row
                st.markdown("### Hành động")
                col_edit, col_delete = st.columns(2)
                with col_edit:
                    if st.button("✏️ Sửa", key=f"edit_{field.get('id', i)}", help="Chỉnh sửa field", use_container_width=True):
                        st.session_state.editing_field = field
                        st.rerun()
                with col_delete:
                    if st.button("🗑️ Xóa", key=f"delete_{field.get('id', i)}", help="Xóa field", use_container_width=True):
                        if st.session_state.get('confirm_delete', False):
                            if db.delete_user_field(field.get('id', ''), st.user.email):
                                st.success("✅ Field đã được xóa!")
                                del st.session_state['confirm_delete']
                                st.rerun()
                            else:
                                st.error("❌ Lỗi khi xóa field")
                        else:
                            st.session_state.confirm_delete = True
                            st.warning(f"Xác nhận xóa '{field.get('name')}'?")
                            if st.button("Xác nhận Xóa", type="primary", key=f"confirm_delete_{field.get('id', i)}"):
                                st.session_state.confirm_delete = True
                                st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
            
    if st.button("➕ Add New Field", type="primary", use_container_width=True, help="Tạo field mới"):
            st.session_state.navigate_to = "Add Field"
            st.rerun()
    
    # Footer or additional info
    
    st.markdown("*Dữ liệu được cập nhật thời gian thực. Nguồn: TerraSync AI*")