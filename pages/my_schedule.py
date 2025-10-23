# pages/my_schedule.py - Enhanced Schedule View
import streamlit as st
import plotly.express as px
import pandas as pd
from database import db
from api_placeholders import terrasync_apis
from datetime import datetime, timedelta

def render_schedule():
    st.title("📅 Irrigation Schedule & Planning")
    st.markdown("Manage your irrigation schedule and water planning")
    
    # Lấy fields từ database
    user_fields = db.get_user_fields(st.user.email) if hasattr(st, 'user') and st.user.is_logged_in else []
    
    if not user_fields:
        st.warning("No fields found. Please add fields first.")
        return
    
    # Field selection
    field_options = {f"{field.get('name', 'Unnamed')} ({field.get('crop', 'Unknown')})": field for field in user_fields}
    selected_field_name = st.selectbox("Select Field", options=list(field_options.keys()))
    selected_field = field_options[selected_field_name]
    
    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["📊 Current Schedule", "🔮 Weather Forecast", "⚙️ Schedule Settings"])
    
    with tab1:
        render_current_schedule(selected_field)
    
    with tab2:
        render_weather_forecast(selected_field)
    
    with tab3:
        render_schedule_settings(selected_field)

def render_current_schedule(field):
    """Current irrigation schedule"""
    st.subheader("📊 Current Irrigation Schedule")
    
    # Generate schedule for selected field
    if st.button("🔄 Generate New Schedule", type="primary"):
        with st.spinner("Generating irrigation schedule..."):
            # Get weather data
            weather_data = terrasync_apis.get_weather_forecast(
                field.get('lat', 20.45), 
                field.get('lon', 106.32), 
                7
            )
            
            # Calculate irrigation schedule
            schedule_data = terrasync_apis.calculate_irrigation_schedule(field, weather_data.get('forecast', {}))
            
            if schedule_data["status"] == "success":
                st.session_state.current_schedule = schedule_data
                st.success("✅ Schedule generated successfully!")
                st.rerun()
            else:
                st.error("❌ Failed to generate schedule")
    
    # Display schedule
    if "current_schedule" in st.session_state:
        schedule = st.session_state.current_schedule
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Weekly Water", f"{schedule['total_weekly_water']:.1f} L")
        with col2:
            st.metric("Efficiency Rating", schedule['efficiency_rating'])
        with col3:
            st.metric("Cost Estimate", f"${schedule['cost_estimate']:.2f}")
        with col4:
            st.metric("Field Area", f"{field.get('area', 0):.2f} ha")
        
        # Schedule chart
        schedule_df = pd.DataFrame(schedule['schedule'])
        
        fig = px.bar(
            schedule_df,
            x='date',
            y='water_liters',
            title='Daily Water Requirements (Next 7 Days)',
            labels={'water_liters': 'Water (Liters)', 'date': 'Date'},
            color='water_liters',
            color_continuous_scale='Blues'
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Detailed schedule table
        st.subheader("📋 Detailed Schedule")
        
        # Format schedule for display
        display_schedule = []
        for day in schedule['schedule']:
            display_schedule.append({
                'Date': day['date'],
                'Water (L)': f"{day['water_liters']:.1f}",
                'Irrigation Time': day['irrigation_time'],
                'Duration (min)': day['duration_minutes'],
                'Efficiency': f"{day['efficiency']*100:.1f}%"
            })
        
        st.dataframe(
            pd.DataFrame(display_schedule),
            use_container_width=True,
            hide_index=True
        )
        
        # Export schedule
        if st.button("📤 Export Schedule"):
            csv = pd.DataFrame(display_schedule).to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"irrigation_schedule_{field.get('name', 'field')}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    else:
        st.info("Click 'Generate New Schedule' to create your irrigation plan")

def render_weather_forecast(field):
    """Weather forecast and recommendations"""
    st.subheader("🌤️ Weather Forecast & Recommendations")
    
    # Get weather forecast
    if st.button("🌤️ Get Weather Forecast", type="primary"):
        with st.spinner("Fetching weather data..."):
            weather_data = terrasync_apis.get_weather_forecast(
                field.get('lat', 20.45), 
                field.get('lon', 106.32), 
                7
            )
            
            if weather_data["status"] == "success":
                st.session_state.weather_forecast = weather_data
                st.success("✅ Weather data retrieved!")
                st.rerun()
            else:
                st.error("❌ Failed to get weather data")
    
    if "weather_forecast" in st.session_state:
        weather = st.session_state.weather_forecast
        forecast = weather.get("forecast", {})
        
        if "daily" in forecast:
            daily_data = forecast["daily"]
            
            # Weather metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                today_temp = daily_data["temperature_2m_max"][0] if daily_data["temperature_2m_max"] else 0
                st.metric("Today's Max Temp", f"{today_temp:.1f}°C")
            
            with col2:
                today_precip = daily_data["precipitation_sum"][0] if daily_data["precipitation_sum"] else 0
                st.metric("Today's Precipitation", f"{today_precip:.1f} mm")
            
            with col3:
                today_wind = daily_data["wind_speed_10m_max"][0] if daily_data["wind_speed_10m_max"] else 0
                st.metric("Today's Max Wind", f"{today_wind:.1f} m/s")
            
            with col4:
                avg_temp = sum(daily_data["temperature_2m_max"]) / len(daily_data["temperature_2m_max"]) if daily_data["temperature_2m_max"] else 0
                st.metric("7-Day Avg Temp", f"{avg_temp:.1f}°C")
            
            # Weather chart
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            
            dates = daily_data["time"]
            temps_max = daily_data["temperature_2m_max"]
            temps_min = daily_data["temperature_2m_min"]
            precip = daily_data["precipitation_sum"]
            wind = daily_data["wind_speed_10m_max"]
            
            fig = make_subplots(
                rows=3, cols=1,
                subplot_titles=('Temperature (°C)', 'Precipitation (mm)', 'Wind Speed (m/s)'),
                vertical_spacing=0.1
            )
            
            # Temperature
            fig.add_trace(
                go.Scatter(x=dates, y=temps_max, name='Max Temp', line=dict(color='red')),
                row=1, col=1
            )
            fig.add_trace(
                go.Scatter(x=dates, y=temps_min, name='Min Temp', line=dict(color='blue')),
                row=1, col=1
            )
            
            # Precipitation
            fig.add_trace(
                go.Bar(x=dates, y=precip, name='Precipitation', marker_color='lightblue'),
                row=2, col=1
            )
            
            # Wind
            fig.add_trace(
                go.Scatter(x=dates, y=wind, name='Wind Speed', line=dict(color='green')),
                row=3, col=1
            )
            
            fig.update_layout(height=600, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
            
            # Irrigation recommendations
            st.subheader("💧 Irrigation Recommendations")
            
            total_precip = sum(precip)
            avg_temp = sum(temps_max) / len(temps_max)
            
            if total_precip > 20:
                st.info("🌧️ High precipitation expected. Consider reducing irrigation by 30%.")
            elif total_precip < 5 and avg_temp > 30:
                st.warning("☀️ Hot and dry conditions. Consider increasing irrigation by 20%.")
            else:
                st.success("✅ Normal weather conditions. Continue regular irrigation schedule.")
            
            # Risk assessment
            st.subheader("⚠️ Weather Risk Assessment")
            
            risks = []
            if max(wind) > 10:
                risks.append("High wind speeds may affect irrigation efficiency")
            if max(temps_max) > 35:
                risks.append("High temperatures may increase water demand")
            if total_precip > 30:
                risks.append("Heavy rainfall may cause waterlogging")
            
            if risks:
                for risk in risks:
                    st.warning(f"⚠️ {risk}")
            else:
                st.success("✅ No significant weather risks detected")

def render_schedule_settings(field):
    """Schedule settings and optimization"""
    st.subheader("⚙️ Schedule Settings & Optimization")
    
    # Current field settings
    st.write("**Current Field Settings:**")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Crop Type", field.get('crop', 'Unknown'))
        st.metric("Growth Stage", field.get('stage', 'Unknown'))
        st.metric("Area", f"{field.get('area', 0):.2f} hectares")
    
    with col2:
        st.metric("Crop Coefficient", field.get('crop_coefficient', 1.0))
        st.metric("Irrigation Efficiency", f"{field.get('irrigation_efficiency', 85)}%")
        st.metric("Current Status", field.get('status', 'Unknown'))
    
    # Optimization settings
    st.subheader("🔧 Optimization Settings")
    
    with st.form("optimization_settings"):
        col1, col2 = st.columns(2)
        
        with col1:
            target_efficiency = st.slider("Target Irrigation Efficiency (%)", 70, 95, field.get('irrigation_efficiency', 85))
            water_saving_mode = st.checkbox("Water Saving Mode", value=False)
            weather_adjustment = st.checkbox("Auto Weather Adjustment", value=True)
        
        with col2:
            irrigation_frequency = st.selectbox("Irrigation Frequency", ["Daily", "Every 2 days", "Every 3 days", "Weekly"])
            preferred_time = st.selectbox("Preferred Irrigation Time", ["Early Morning (6-8 AM)", "Evening (6-8 PM)", "Flexible"])
            max_duration = st.number_input("Max Irrigation Duration (hours)", 1, 12, 4)
        
        if st.form_submit_button("💾 Save Settings", type="primary"):
            # Update field settings
            update_data = {
                'irrigation_efficiency': target_efficiency,
                'water_saving_mode': water_saving_mode,
                'weather_adjustment': weather_adjustment,
                'irrigation_frequency': irrigation_frequency,
                'preferred_time': preferred_time,
                'max_duration': max_duration
            }
            
            if db.update_user_field(field.get('id', ''), st.user.email, update_data):
                st.success("✅ Settings saved successfully!")
                st.rerun()
            else:
                st.error("❌ Failed to save settings")
    
    # Optimization recommendations
    st.subheader("💡 Optimization Recommendations")
    
    # Analyze current settings and provide recommendations
    current_efficiency = field.get('irrigation_efficiency', 85)
    
    if current_efficiency < 80:
        st.warning("⚠️ Low irrigation efficiency detected. Consider:")
        st.write("- Check for leaks in irrigation system")
        st.write("- Optimize irrigation timing")
        st.write("- Use drip irrigation for better efficiency")
    elif current_efficiency > 90:
        st.success("✅ Excellent irrigation efficiency!")
    else:
        st.info("ℹ️ Good irrigation efficiency. Consider:")
        st.write("- Fine-tune irrigation timing")
        st.write("- Monitor soil moisture levels")
        st.write("- Adjust based on weather conditions")
    
    # Water usage analysis
    st.subheader("📊 Water Usage Analysis")
    
    # Simulate water usage data
    import numpy as np
    
    days = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
    water_usage = np.random.normal(100, 20, len(days))
    
    fig = px.line(
        x=days,
        y=water_usage,
        title='Water Usage Trend (Last 30 Days)',
        labels={'x': 'Date', 'y': 'Water Usage (Liters)'}
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Usage statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Avg Daily Usage", f"{np.mean(water_usage):.1f} L")
    with col2:
        st.metric("Total Monthly", f"{np.sum(water_usage):.1f} L")
    with col3:
        st.metric("Efficiency Score", f"{current_efficiency}%")