# pages/settings.py - Enhanced Settings
import streamlit as st
from database import db
from datetime import datetime

def render_settings():
    st.title("⚙️ Settings & Configuration")
    st.markdown("Manage your TerraSync IoT account and application settings")
    
    # Tabs for different settings
    tab1, tab2, tab3, tab4 = st.tabs(["👤 Profile", "🌍 Location", "🔧 Preferences", "🔐 Security"])
    
    with tab1:
        render_profile_settings()
    
    with tab2:
        render_location_settings()
    
    with tab3:
        render_preferences()
    
    with tab4:
        render_security_settings()

def render_profile_settings():
    """User profile settings"""
    st.subheader("👤 Profile Settings")
    
    # Get current user data
    if hasattr(st, 'user') and st.user.is_logged_in:
        user_data = db.get_user_by_email(st.user.email)
        
        with st.form("profile_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Full Name", value=user_data.get('name', '') if user_data else st.user.name or '')
                email = st.text_input("Email", value=st.user.email, disabled=True)
                phone = st.text_input("Phone Number", value=user_data.get('phone', '') if user_data else '')
            
            with col2:
                organization = st.text_input("Organization/Farm Name", value=user_data.get('organization', '') if user_data else '')
                role = st.selectbox("Role", ["Farmer", "Farm Manager", "Agricultural Engineer", "Researcher", "Other"])
                experience = st.selectbox("Farming Experience", ["Beginner (< 1 year)", "Intermediate (1-5 years)", "Advanced (5-10 years)", "Expert (10+ years)"])
            
            bio = st.text_area("Bio/Description", value=user_data.get('bio', '') if user_data else '', height=100)
            
            if st.form_submit_button("💾 Save Profile", type="primary"):
                # Update user data
                update_data = {
                    'name': name,
                    'phone': phone,
                    'organization': organization,
                    'role': role,
                    'experience': experience,
                    'bio': bio,
                    'updated_at': datetime.now().isoformat()
                }
                
                if user_data:
                    db.update("users", {"email": st.user.email}, update_data)
                else:
                    # Create new user record
                    user_data = {
                        'email': st.user.email,
                        'name': name,
                        'phone': phone,
                        'organization': organization,
                        'role': role,
                        'experience': experience,
                        'bio': bio,
                        'first_login': datetime.now().isoformat(),
                        'last_login': datetime.now().isoformat()
                    }
                    db.add("users", user_data)
                
                st.success("✅ Profile updated successfully!")
                st.rerun()
    else:
        st.warning("Please log in to access profile settings")

def render_location_settings():
    """Location and farm settings"""
    st.subheader("🌍 Location & Farm Settings")
    
    # Get user's default location
    user_data = db.get_user_by_email(st.user.email) if hasattr(st, 'user') and st.user.is_logged_in else None
    default_location = user_data.get('default_location', {"lat": 20.450123, "lon": 106.325678}) if user_data else {"lat": 20.450123, "lon": 106.325678}
    
    with st.form("location_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Default Farm Location**")
            lat = st.number_input("Latitude", value=default_location.get('lat', 20.450123), format="%.6f")
            lon = st.number_input("Longitude", value=default_location.get('lon', 106.325678), format="%.6f")
            timezone = st.selectbox("Timezone", ["Asia/Ho_Chi_Minh", "UTC", "America/New_York", "Europe/London"])
        
        with col2:
            st.write("**Regional Settings**")
            country = st.selectbox("Country", ["Vietnam", "United States", "India", "China", "Brazil", "Other"])
            language = st.selectbox("Language", ["Vietnamese", "English", "Chinese", "Spanish", "Portuguese"])
            units = st.selectbox("Measurement Units", ["Metric (m, kg, °C)", "Imperial (ft, lb, °F)"])
        
        if st.form_submit_button("💾 Save Location Settings", type="primary"):
            # Update location settings
            location_data = {
                'default_location': {"lat": lat, "lon": lon},
                'timezone': timezone,
                'country': country,
                'language': language,
                'units': units,
                'updated_at': datetime.now().isoformat()
            }
            
            if user_data:
                db.update("users", {"email": st.user.email}, location_data)
            else:
                # Create new user record
                user_data = {
                    'email': st.user.email,
                    'default_location': {"lat": lat, "lon": lon},
                    'timezone': timezone,
                    'country': country,
                    'language': language,
                    'units': units,
                    'first_login': datetime.now().isoformat(),
                    'last_login': datetime.now().isoformat()
                }
                db.add("users", user_data)
            
            st.success("✅ Location settings saved!")
            st.rerun()
    
    # Show map preview
    if lat and lon:
        import folium
        from streamlit_folium import st_folium
        
        m = folium.Map(location=[lat, lon], zoom_start=10)
        folium.Marker([lat, lon], popup="Farm Location").add_to(m)
        st_folium(m, width=700, height=400)

def render_preferences():
    """Application preferences"""
    st.subheader("🔧 Application Preferences")
    
    # Get user preferences
    user_data = db.get_user_by_email(st.user.email) if hasattr(st, 'user') and st.user.is_logged_in else None
    preferences = user_data.get('preferences', {}) if user_data else {}
    
    with st.form("preferences_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Display Settings**")
            theme = st.selectbox("Theme", ["Light", "Dark", "Auto"])
            dashboard_layout = st.selectbox("Dashboard Layout", ["Compact", "Standard", "Detailed"])
            auto_refresh = st.checkbox("Auto-refresh data", value=preferences.get('auto_refresh', True))
            refresh_interval = st.slider("Refresh interval (seconds)", 30, 300, preferences.get('refresh_interval', 60))
        
        with col2:
            st.write("**Notification Settings**")
            email_notifications = st.checkbox("Email notifications", value=preferences.get('email_notifications', True))
            push_notifications = st.checkbox("Push notifications", value=preferences.get('push_notifications', True))
            weather_alerts = st.checkbox("Weather alerts", value=preferences.get('weather_alerts', True))
            irrigation_reminders = st.checkbox("Irrigation reminders", value=preferences.get('irrigation_reminders', True))
        
        st.write("**Data & Privacy**")
        data_sharing = st.checkbox("Share anonymous usage data for improvement", value=preferences.get('data_sharing', False))
        analytics = st.checkbox("Enable analytics tracking", value=preferences.get('analytics', True))
        
        if st.form_submit_button("💾 Save Preferences", type="primary"):
            # Update preferences
            new_preferences = {
                'theme': theme,
                'dashboard_layout': dashboard_layout,
                'auto_refresh': auto_refresh,
                'refresh_interval': refresh_interval,
                'email_notifications': email_notifications,
                'push_notifications': push_notifications,
                'weather_alerts': weather_alerts,
                'irrigation_reminders': irrigation_reminders,
                'data_sharing': data_sharing,
                'analytics': analytics,
                'updated_at': datetime.now().isoformat()
            }
            
            update_data = {'preferences': new_preferences}
            
            if user_data:
                db.update("users", {"email": st.user.email}, update_data)
            else:
                # Create new user record
                user_data = {
                    'email': st.user.email,
                    'preferences': new_preferences,
                    'first_login': datetime.now().isoformat(),
                    'last_login': datetime.now().isoformat()
                }
                db.add("users", user_data)
            
            st.success("✅ Preferences saved!")
            st.rerun()
    
    # API Configuration
    st.subheader("🔌 API Configuration")
    
    with st.expander("API Keys & Integrations"):
        st.write("**Current API Status:**")
        
        # Check API keys
        api_key = st.secrets.get("gemini", {}).get("api_key", "")
        if api_key:
            st.success("✅ Gemini API: Configured")
        else:
            st.error("❌ Gemini API: Not configured")
        
        # Weather API
        st.info("🌤️ Weather API: Open-Meteo (Free)")
        
        # Satellite API
        st.info("🛰️ Satellite API: OpenET (NASA)")
        
        # IoT API
        st.info("📡 IoT API: Local server")
        
        st.write("**Note**: API keys are configured in `.streamlit/secrets.toml` file")

def render_security_settings():
    """Security and account settings"""
    st.subheader("🔐 Security & Account")
    
    if hasattr(st, 'user') and st.user.is_logged_in:
        user_data = db.get_user_by_email(st.user.email)
        
        # Account information
        st.write("**Account Information:**")
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Email", st.user.email)
            st.metric("Account Status", "Active" if user_data.get('is_active', True) else "Inactive")
        
        with col2:
            first_login = user_data.get('first_login', 'Unknown') if user_data else 'Unknown'
            last_login = user_data.get('last_login', 'Unknown') if user_data else 'Unknown'
            st.metric("Member Since", first_login[:10] if first_login != 'Unknown' else 'Unknown')
            st.metric("Last Login", last_login[:10] if last_login != 'Unknown' else 'Unknown')
        
        # Data management
        st.subheader("📊 Data Management")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📤 Export My Data", type="secondary"):
                # Export user data
                export_data = {
                    "user_info": user_data,
                    "fields": db.get_user_fields(st.user.email),
                    "iot_hubs": db.get("iot_hubs", {"user_email": st.user.email}),
                    "export_date": datetime.now().isoformat()
                }
                
                import json
                json_data = json.dumps(export_data, indent=2, ensure_ascii=False)
                
                st.download_button(
                    label="Download JSON",
                    data=json_data,
                    file_name=f"terrasync_data_{st.user.email}_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json"
                )
        
        with col2:
            if st.button("🗑️ Delete Account", type="secondary"):
                st.warning("⚠️ This action cannot be undone!")
                if st.button("Confirm Delete", type="primary"):
                    # Delete user data
                    db.delete("users", {"email": st.user.email})
                    db.delete("fields", {"user_email": st.user.email})
                    db.delete("iot_hubs", {"user_email": st.user.email})
                    
                    st.success("✅ Account deleted successfully!")
                    st.info("Please refresh the page to see changes")
        
        # Session management
        st.subheader("🔑 Session Management")
        
        if st.button("🚪 Logout All Sessions", type="secondary"):
            st.info("All sessions will be logged out. You'll need to log in again.")
            # In a real app, this would invalidate all sessions
        
        # Privacy settings
        st.subheader("🔒 Privacy Settings")
        
        with st.form("privacy_form"):
            profile_visibility = st.selectbox("Profile Visibility", ["Public", "Private", "Friends Only"])
            data_retention = st.selectbox("Data Retention", ["Keep all data", "Auto-delete after 1 year", "Auto-delete after 2 years"])
            marketing_emails = st.checkbox("Receive marketing emails", value=user_data.get('marketing_emails', False) if user_data else False)
            
            if st.form_submit_button("💾 Save Privacy Settings", type="primary"):
                privacy_data = {
                    'profile_visibility': profile_visibility,
                    'data_retention': data_retention,
                    'marketing_emails': marketing_emails,
                    'updated_at': datetime.now().isoformat()
                }
                
                if user_data:
                    db.update("users", {"email": st.user.email}, privacy_data)
                else:
                    user_data = {
                        'email': st.user.email,
                        'profile_visibility': profile_visibility,
                        'data_retention': data_retention,
                        'marketing_emails': marketing_emails,
                        'first_login': datetime.now().isoformat(),
                        'last_login': datetime.now().isoformat()
                    }
                    db.add("users", user_data)
                
                st.success("✅ Privacy settings saved!")
                st.rerun()
    else:
        st.warning("Please log in to access security settings")
    
    # System information
    st.subheader("ℹ️ System Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Application Version:** 1.0.0")
        st.write("**Database:** SQLite/JSON")
        st.write("**Last Updated:** 2025-01-15")
    
    with col2:
        st.write("**Server:** Local")
        st.write("**Environment:** Development")
        st.write("**Support:** support@terrasync.io")