# pages/settings.py - Simple Form Layout
import streamlit as st

def render_settings():
    st.header("Settings")

    # Location Form - Compact
    lat = st.number_input("Latitude", value=st.session_state.farm_location['lat'])
    lon = st.number_input("Longitude", value=st.session_state.farm_location['lon'])
    if st.button("Update Location"):
        st.session_state.farm_location = {'lat': lat, 'lon': lon}
        st.success("Updated!")

    # Other Settings - Bullet List
    st.subheader("Integrations")
    st.write("- Gemini API: Configured")
    st.write("- Data Sources: Mocked")