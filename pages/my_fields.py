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
            <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="{color}" stroke-width="3" stroke-dasharray="{value}, 100" />
        </svg>
        <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 14px; font-weight: bold; color: #495057;">{value}%</div>
    </div>
    """
    return html

def render_fields():
    st.set_page_config(page_title="My Fields", page_icon="👩🏻‍🌾", layout="wide")
    
    # Lấy fields từ database
    user_fields = db.get_user_fields(st.user.email) if hasattr(st, 'user') and st.user.is_logged_in else []
    fields = user_fields
    
    # Cập nhật session state
    st.session_state.fields = fields
    
    if "hydration_jobs" not in st.session_state:
        st.session_state.hydration_jobs = {'completed': 2, 'active': 1, 'remaining': 3}
    
    # Header Cards
    with st.container(border=True, vertical_alignment='center'):
        st.markdown("### 💧 Hydration Jobs")
        st.markdown("Cùng theo dõi tiến độ tưới nước hôm nay nhé:")

        box_css = """
            <div style="
                border: 2px solid {color};
                border-radius: 10px;
                padding: 12px;
                text-align: center;
                margin-bottom: 10px;
            ">
                <h4 style="margin: 0; color: {color};">{label}</h4>
                <p style="font-size: 24px; font-weight: bold; margin: 5px 0;">{value}</p>
            </div>
        """

        cols = st.columns(3)
        with cols[0]:
            st.markdown(box_css.format(
                label="✅ Completed",
                value=st.session_state.hydration_jobs['completed'],
                color="#2e7d32"  # xanh lá đậm
            ), unsafe_allow_html=True)

        with cols[1]:
            st.markdown(box_css.format(
                label="🚿 Active",
                value=st.session_state.hydration_jobs['active'],
                color="#0277bd"  # xanh dương đậm
            ), unsafe_allow_html=True)

        with cols[2]:
            st.markdown(box_css.format(
                label="⏳ Remaining",
                value=st.session_state.hydration_jobs['remaining'],
                color="#f57c00"  # cam đậm
            ), unsafe_allow_html=True)

    
    # All Fields
    st.subheader("All Fields")
    search_query = st.text_input("", placeholder="Search fields", label_visibility="collapsed")
    
    # Filter fields based on search
    filtered_fields = [f for f in fields if search_query.lower() in f.get('name', '').lower() or search_query.lower() in f.get('crop', '').lower()]
    
    if not filtered_fields:
        st.info("No fields found. Add your first field using the button above.")
        return
    
    for field in filtered_fields:
        status_colors = {
            'hydrated': {'bg': '#d4edda', 'text': '#155724', 'overlay': 'green'},
            'dehydrated': {'bg': '#fff3cd', 'text': '#856404', 'overlay': 'orange'},
            'severely_dehydrated': {'bg': '#f8d7da', 'text': '#721c24', 'overlay': 'red'}
        }
        color_info = status_colors.get(field.get('status', 'hydrated'), status_colors['hydrated'])
        
        with st.container(border=True):
            cols = st.columns([2, 5, 2, 2])
            
            with cols[0]:
                # Satellite map preview
                if 'polygon' in field and field['polygon']:
                    m = folium.Map(
                        location=[field.get('lat', 20.45), field.get('lon', 106.32)], 
                        zoom_start=16, 
                        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                        attr="EWI"
                    )
                    folium.Polygon(
                        locations=field['polygon'],
                        color=color_info['overlay'],
                        fill=True,
                        fill_color=color_info['overlay'],
                        fill_opacity=0.5,
                        weight=2
                    ).add_to(m)
                    st_folium(m, width=200, height=150, returned_objects=[], key=f"map_{field.get('id', 'unknown')}")
                else:
                    st.image("https://upload.wikimedia.org/wikipedia/commons/6/65/No-Image-Placeholder.svg", caption="No map available")
            
            with cols[1]:
                st.markdown(f"**{field.get('name', 'Unnamed Field')}**  {field.get('area', 0):.2f} hectares")
                status_badge = f'<span style="background-color: {color_info["bg"]}; color: {color_info["text"]}; padding: 6px 12px; border-radius: 20px; font-weight: bold;">Crop Hydration  {field.get("status", "hydrated").title().replace("_", " ")}</span>'
                st.markdown(status_badge, unsafe_allow_html=True)
                st.markdown(f"Today's Water  {field.get('today_water', 0)} liters")
                st.markdown(f"Crop: {field.get('crop', 'Unknown')} | Stage: {field.get('stage', 'Unknown')}")
            
            with cols[2]:
                st.markdown('<p style="text-align: right; color: #6c757d; font-size: 12px;">TIME NEEDED</p>', unsafe_allow_html=True)
                st.markdown(f'<p style="text-align: right; font-size: 18px; font-weight: bold;">{field.get("time_needed", 0)} hours</p>', unsafe_allow_html=True)
            
            with cols[3]:
                st.markdown('<p style="text-align: right; color: #6c757d; font-size: 12px;">STATUS</p>', unsafe_allow_html=True)
                st.markdown(render_progress(field.get('progress', 0)), unsafe_allow_html=True)
                
                # Action buttons
                col_edit, col_delete = st.columns(2)
                with col_edit:
                    if st.button("✏️", key=f"edit_{field.get('id', 'unknown')}", help="Edit field"):
                        st.session_state.editing_field = field
                with col_delete:
                    if st.button("🗑️", key=f"delete_{field.get('id', 'unknown')}", help="Delete field"):
                        if db.delete_user_field(field.get('id', ''), st.user.email):
                            st.success("Field deleted!")
                            st.rerun()
                        else:
                            st.error("Failed to delete field")
