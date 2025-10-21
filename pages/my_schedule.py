# pages/my_schedule.py - Grid View for Schedule
import streamlit as st

def render_schedule():
    st.header("My Schedule")

    # Schedule in Table - Clean and Readable
    schedule_df = st.dataframe(
        st.session_state.schedule,
        column_config={
            "date": "Date",
            "water": "Water (gal)",
            "end_time": "End Time"
        },
        use_container_width=True
    )