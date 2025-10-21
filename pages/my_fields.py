import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd

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
    
    if "hydration_jobs" not in st.session_state:
        st.session_state.hydration_jobs = {'completed': 2, 'active': 1, 'remaining': 3}
        
    if "fields" not in st.session_state:
        st.session_state.fields = [
            {
                'id': 1, 
                'name': 'Blueberry Field', 
                'crop': 'Blueberry', 
                'area': 675.45,
                'status': 'hydrated', 
                'today_water': 80, 
                'time_needed': 4,
                'progress': 95, 
                'days_to_harvest': 48, 
                'lat': 35.6229, 
                'lon': -120.6933, 
                'stage': 'Adult',
                'polygon': [
                    [35.6225, -120.6938],
                    [35.6230, -120.6938],
                    [35.6230, -120.6928],
                    [35.6225, -120.6928]
                ]
            },
            {
                'id': 2, 
                'name': 'Avocado Field', 
                'crop': 'Avocado', 
                'area': 585.39,
                'status': 'dehydrated', 
                'today_water': 63, 
                'time_needed': 3.5,
                'progress': 32, 
                'days_to_harvest': 120, 
                'lat': 35.6235, 
                'lon': -120.6940, 
                'stage': 'Adult',
                'polygon': [
                    [35.6230, -120.6945],
                    [35.6240, -120.6945],
                    [35.6240, -120.6935],
                    [35.6230, -120.6935]
                ]
            },
            {
                'id': 3, 
                'name': 'Corn Field A', 
                'crop': 'Corn', 
                'area': 720.48,
                'status': 'severely_dehydrated', 
                'today_water': 157, 
                'time_needed': 11,
                'progress': 0, 
                'days_to_harvest': 90, 
                'lat': 35.6215, 
                'lon': -120.6920, 
                'stage': 'Seedling',
                'polygon': [
                    [35.6210, -120.6925],
                    [35.6220, -120.6925],
                    [35.6220, -120.6915],
                    [35.6210, -120.6915]
                ]
            }
        ]
    
    # Header Cards
    col_left, col_right = st.columns([1, 2], border=True, vertical_alignment='center')
    
    with col_left:
        col_v, col_r = st.columns(2)
        with col_v:
            st.markdown('<h3 style="color: #28a745;">Good ★</h3>', unsafe_allow_html=True)
            st.markdown("Fields Overview")
        with col_r:
            if st.button("View Fields >", key="view_fields"):
                pass
            if st.button("Report >", key="report"):
                pass
    
    with col_right:
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
    col_search, col_add = st.columns([8, 1])
    with col_search:
        search_query = st.text_input("", placeholder="Search fields", label_visibility="collapsed")
    with col_add:
        if st.button("+ Add new field", type="primary"):
            st.session_state.add_new = True
    
    if st.session_state.get('add_new', False):
        with st.expander("Add New Field", expanded=True):
            crop = st.selectbox("Crop", ["Blueberry", "Avocado", "Corn"])
            name = st.text_input("Field Name")
            area = st.number_input("Area (acres)", min_value=1.0)
            lat = st.number_input("Latitude", value=35.6229)
            lon = st.number_input("Longitude", value=-120.6933)
            if st.button("Add Field"):
                new_id = max(f['id'] for f in st.session_state.fields) + 1
                new_polygon = [
                    [lat - 0.0005, lon - 0.0005],
                    [lat + 0.0005, lon - 0.0005],
                    [lat + 0.0005, lon + 0.0005],
                    [lat - 0.0005, lon + 0.0005]
                ]
                new_field = {
                    'id': new_id, 
                    'name': name or f"{crop} Field {new_id}", 
                    'crop': crop, 
                    'area': area,
                    'status': 'hydrated', 
                    'today_water': 100, 
                    'time_needed': 2,
                    'progress': 50, 
                    'days_to_harvest': 60, 
                    'lat': lat, 
                    'lon': lon, 
                    'stage': 'Adult',
                    'polygon': new_polygon
                }
                st.session_state.fields.append(new_field)
                st.session_state.add_new = False
                st.success("Field added!")
                st.rerun()
    
    # Filter fields based on search
    filtered_fields = [f for f in st.session_state.fields if search_query.lower() in f['name'].lower() or search_query.lower() in f['crop'].lower()]
    
    for field in filtered_fields:
        status_colors = {
            'hydrated': {'bg': '#d4edda', 'text': '#155724', 'overlay': 'green'},
            'dehydrated': {'bg': '#fff3cd', 'text': '#856404', 'overlay': 'orange'},
            'severely_dehydrated': {'bg': '#f8d7da', 'text': '#721c24', 'overlay': 'red'}
        }
        color_info = status_colors.get(field['status'], status_colors['hydrated'])
        
        with st.container(border=True):
            cols = st.columns([2, 5, 2, 2])
            
            with cols[0]:
                # Satellite map preview
                if 'polygon' in field:
                    m = folium.Map(
                        location=[field['lat'], field['lon']], 
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
                    st_folium(m, width=200, height=150, returned_objects=[], key=f"map_{field['id']}")
                else:
                    st.image("https://upload.wikimedia.org/wikipedia/commons/6/65/No-Image-Placeholder.svg", caption="No map available")
            
            with cols[1]:
                st.markdown(f"**{field['name']}**  {field['area']} acres")
                status_badge = f'<span style="background-color: {color_info["bg"]}; color: {color_info["text"]}; padding: 6px 12px; border-radius: 20px; font-weight: bold;">Crop Hydration  {field["status"].title().replace("_", " ")}</span>'
                st.markdown(status_badge, unsafe_allow_html=True)
                st.markdown(f"Today's Water  {field['today_water']}gallons")
            
            with cols[2]:
                st.markdown('<p style="text-align: right; color: #6c757d; font-size: 12px;">TIME NEEDED</p>', unsafe_allow_html=True)
                st.markdown(f'<p style="text-align: right; font-size: 18px; font-weight: bold;">{field["time_needed"]} hours</p>', unsafe_allow_html=True)
            
            with cols[3]:
                st.markdown('<p style="text-align: right; color: #6c757d; font-size: 12px;">STATUS</p>', unsafe_allow_html=True)
                st.markdown(render_progress(field['progress']), unsafe_allow_html=True)

render_fields()