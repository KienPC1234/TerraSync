# pages/my_schedule.py - Enhanced Schedule View
import streamlit as st
import plotly.express as px
import pandas as pd

def render_schedule():
    st.header("My Schedule")
    
    if not st.session_state.get('schedule'):
        st.warning("No schedule data available")
        return
    
    # Create DataFrame from schedule
    schedule_df = pd.DataFrame(st.session_state.schedule)
    
    # Visualize water requirements
    fig = px.bar(
        schedule_df,
        x='date',
        y='water',
        title='Water Requirements (Next 7 Days)',
        labels={'water': 'Water (gallons)', 'date': 'Date'},
        color='water',
        color_continuous_scale='Blues'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Detailed schedule table
    st.subheader("Detailed Schedule")
    st.dataframe(
        schedule_df,
        column_config={
            "date": "Date",
            "water": st.column_config.ProgressColumn(
                "Water (gal)",
                format="%f",
                min_value=0,
                max_value=200
            ),
            "end_time": "End Time"
        },
        use_container_width=True
    )