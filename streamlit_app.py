import streamlit as st
from streamlit_option_menu import option_menu
import google.generativeai as genai
import os
from datetime import datetime

# Import các page
from pages.dashboard import render_dashboard
from pages.chat import render_chat
from pages.my_fields import render_fields
from pages.my_schedule import render_schedule
from pages.settings import render_settings
from pages.help_center import render_help_center
from pages.login import render_login, logout
from pages.iot_management import render_iot_management
from pages.ai_field_detection import render_ai_field_detection
from pages.satellite_view import render_satellite_view
from pages.add_field import render_add_field
from utils import (
    fetch_alerts,
    fetch_history,
    fetch_latest_telemetry,
    generate_schedule,
    get_fields_from_db,
    predict_water_needs
)
from database import db


# -----------------------------
# ✅ Cấu hình Gemini API
# -----------------------------
api_key = (
    os.getenv("GEMINI_API_KEY")
    or st.secrets.get("gemini", {}).get("api_key", "")
)
if not api_key:
    st.error(
        "⚠️ Missing Gemini API key! Please set GEMINI_API_KEY or secrets.toml.")
else:
    genai.configure(api_key=api_key)

st.set_page_config(layout="wide")

# -----------------------------
# ✅ Khởi tạo Session States
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "show_ai" not in st.session_state:
    st.session_state.show_ai = False

if "hydration_jobs" not in st.session_state:
    st.session_state.hydration_jobs = {
        "completed": 0, "active": 0, "remaining": 0}

if "demo_mode" not in st.session_state:
    st.session_state.demo_mode = st.secrets.get(
        "demo", {}).get(
        "enabled", False)

if "fields" not in st.session_state:
    st.session_state.fields = get_fields_from_db()


def classify_moisture(value: float) -> str:
    if value < 25:
        return "severely_dehydrated"
    if value < 45:
        return "dehydrated"
    if value < 60:
        return "moderate"
    return "hydrated"


def update_fields_from_telemetry():
    telemetry = st.session_state.get("telemetry")
    if not telemetry:
        return
    soil_nodes = telemetry.get("data", {}).get("soil_nodes", [])
    node_lookup = {
        node.get("node_id"): node.get(
            "sensors",
            {}) for node in soil_nodes}
    totals = {"completed": 0, "active": 0, "remaining": 0}
    for field in st.session_state.fields:
        sensors = node_lookup.get(field.get("node_id"))
        if not sensors:
            continue
        moisture = sensors.get("soil_moisture")
        temperature = sensors.get("soil_temperature")

        # Predict water needs using the new function
        predicted_water = predict_water_needs(field, telemetry)
        field["today_water"] = predicted_water
        # Simple estimation for time needed based on predicted water
        field["time_needed"] = round(
            predicted_water / 20, 1) if predicted_water > 0 else 0.0

        if moisture is not None:
            field["live_moisture"] = round(moisture, 1)
            status = classify_moisture(moisture)
            field["status"] = status
            field["status_label"] = status.replace("_", " ").title()
            field["progress"] = max(0, min(100, round(moisture * 1.5)))
            bucket = {
                "hydrated": "completed",
                "moderate": "active",
                "dehydrated": "active",
                "severely_dehydrated": "remaining",
            }.get(status)
            if bucket:
                totals[bucket] += 1
        if temperature is not None:
            field["soil_temperature"] = round(temperature, 1)
        if "area" in field:
            field["area_display"] = f"{field['area']:.2f} acres"
        if field.get("today_water"):
            liters = int(field["today_water"])
            field["water_usage"] = f"{liters} liters/day"
    if any(totals.values()):
        st.session_state.hydration_jobs = totals


def load_iot_snapshot(force: bool = False):
    if force or "telemetry" not in st.session_state:
        st.session_state.telemetry = fetch_latest_telemetry()
        st.session_state.history = fetch_history(limit=30)
        st.session_state.alerts = fetch_alerts(limit=20)
        st.session_state.last_sync = st.session_state.telemetry.get("timestamp")
    update_fields_from_telemetry()
    st.session_state.schedule = generate_schedule(
        st.session_state.get("telemetry"))


# -----------------------------
# ✅ Login Check (OAuth) & User Management
# -----------------------------
if not st.user.is_logged_in:
    # Nếu chưa login thì hiển thị login page và dừng app
    render_login()
    st.stop()

# Check if user is admin
if st.user.email == "kienpc872009@gmail.com":
    st.session_state.is_admin = True
else:
    st.session_state.is_admin = False


# Lưu user data vào database khi login
if "user_saved" not in st.session_state:
    try:
        user_data = {
            "email": st.user.email,
            "name": st.user.name or "",
            "picture": getattr(st.user, 'picture', '') or "",
            "first_login": datetime.now().isoformat(),
            "last_login": datetime.now().isoformat(),
            "is_active": True
        }

        # Tạo hoặc cập nhật user
        existing_user = db.get_user_by_email(st.user.email)

        if existing_user:
            # Cập nhật user hiện tại
            update_data = {
                "last_login": datetime.now().isoformat(),
                "name": st.user.name or existing_user.get('name', ''),
                "picture": getattr(
                    st.user,
                    'picture',
                    '') or existing_user.get(
                    'picture',
                    '')}
            db.update("users", {"email": st.user.email}, update_data)
            st.session_state.user_saved = True
        else:
            db.add("users", user_data)
            st.session_state.user_saved = True
            st.session_state.new_user = True

    except Exception as e:
        st.error(f"Lỗi lưu thông tin user: {e}")
        print(f"Database error: {e}")

# Hiển thị thông báo cho user mới
if st.session_state.get("new_user", False):
    st.success(
        "🎉 Chào mừng bạn đến với TerraSync IoT! Hãy bắt đầu bằng cách thêm "
        "ruộng đầu tiên của bạn.")
    st.session_state.new_user = False

# -----------------------------
# ✅ Sau khi login — main app
# -----------------------------
load_iot_snapshot()

if st.session_state.pop("refresh_notice", None):
    st.info("IoT data refreshed")

# Set up periodic polling
if "last_poll" not in st.session_state:
    st.session_state.last_poll = datetime.now()

# Check if 30 seconds have passed
if (datetime.now() - st.session_state.last_poll).total_seconds() > 30:
    load_iot_snapshot(force=True)
    st.session_state.last_poll = datetime.now()
    st.session_state.refresh_notice = True
    # st.rerun()

# -----------------------------
# ✅ Sidebar Navigation
# -----------------------------
with st.sidebar:
    selected = option_menu(
        "🌱 TerraSync",
        ["Dashboard", "My Fields", "Add Field", "My Schedule", "Ask CropNet AI",
         "IoT Management", "AI Detection", "Satellite View", "Settings",
         "Help Center"],
        icons=["house", "grid", "plus", "calendar", "chat", "wifi", "robot",
               "image", "gear", "question-circle"],
        default_index=0,
        menu_icon="psychiatry"
    )
    if st.button("🔄 Refresh IoT Data", use_container_width=True):
        load_iot_snapshot(force=True)
        st.session_state.refresh_notice = True
        st.rerun()

    if st.session_state.get("last_sync"):
        st.caption(f"Last sync: {st.session_state.last_sync}")
    if st.button("🚪 Đăng xuất", type="secondary"):
        logout()
        st.rerun()


# -----------------------------
# ✅ Header Section
# -----------------------------
def render_top_section(location="Paso Robles Farm", Page_Title=""):

    user_data = db.get_user_by_email(st.user.email)
    fname = user_data.get('organization', '')
    location = f"{fname} Farm" if fname else location
    date = datetime.now()
    day = date.strftime("%A")
    formatted_date = date.strftime("%B %d, %Y")

    st.markdown("""
    <style>
    .header-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 0;
        margin-bottom: 35px;
    }
    .header-title {
        font-size: 30px;
        font-weight: 600;
        color: #333;
    }
    .header-meta {
        display: flex;
        align-items: center;
        gap: 10px;
        color: #777;
        font-size: 20px;
    }
    .header-meta .divider {
        width: 1px;
        height: 20px;
        background-color: #ddd;
    }
    .location-pill {
        display: flex;
        align-items: center;
        background-color: #d7f1f3;
        color: #222;
        font-weight: 500;
        border-radius: 12px;
        padding: 4px 10px;
        font-size: 20px;
    }
    .location-pill .icon {
        color: #d43f3a;
        margin-right: 6px;
        font-size: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="header-container">
        <div class="header-title">{Page_Title}</div>
        <div class="header-meta">
            <span>{day}</span>
            <span class="divider"></span>
            <span>{formatted_date}</span>
            <span class="divider"></span>
            <div class="location-pill">
                <span class="icon">🗺️</span> {location}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# -----------------------------
# ✅ Điều hướng giữa các page
# -----------------------------

# Check for navigation request from add_field
if st.session_state.get("navigate_to"):
    target_page = st.session_state.navigate_to
    # Clear navigation request
    del st.session_state.navigate_to

    # Find the index of target page
    page_options = [
        "Dashboard",
        "My Fields",
        "Add Field",
        "My Schedule",
        "Ask Sprout AI",
        "IoT Management",
        "AI Detection",
        "Satellite View",
        "Settings",
        "Help Center"]
    if target_page in page_options:
        target_index = page_options.index(target_page)
        # Update selected page
        selected = target_page

if selected == "Dashboard":
    render_top_section(Page_Title=f"👋 Welcome back, {st.user.name}")
    render_dashboard()

elif selected == "Ask CropNet AI":
    render_chat()

elif selected == "My Fields":
    render_top_section(Page_Title="Fields Overview")
    render_fields()

elif selected == "Add Field":
    render_add_field()

elif selected == "My Schedule":
    render_schedule()

elif selected == "Settings":
    render_settings()

elif selected == "IoT Management":
    render_iot_management()

elif selected == "AI Detection":
    render_ai_field_detection()

elif selected == "Satellite View":
    render_satellite_view()

elif selected == "Help Center":
    render_help_center()
