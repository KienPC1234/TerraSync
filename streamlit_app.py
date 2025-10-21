import streamlit as st
from streamlit_option_menu import option_menu
import google.generativeai as genai
import os
from datetime import datetime
from pages import dashboard, chat, my_fields, my_schedule, settings, help_center
from pages.dashboard import render_dashboard
from pages.chat import render_chat
from pages.my_fields import render_fields
from pages.my_schedule import render_schedule
from pages.settings import render_settings
from pages.help_center import render_help_center


# -----------------------------
# ✅ Configure Gemini correctly
# -----------------------------
api_key = (
    os.getenv("GEMINI_API_KEY")
    or st.secrets.get("gemini", {}).get("api_key", "")
)
if not api_key:
    st.error("⚠️ Missing Gemini API key! Please set GEMINI_API_KEY or secrets.toml.")
genai.configure(api_key=api_key)

# -----------------------------
# ✅ Initialize Session States
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []  # for chat history

if "show_ai" not in st.session_state:
    st.session_state.show_ai = False



if "schedule" not in st.session_state:
    try:
        from utils import generate_schedule
        st.session_state.schedule = generate_schedule()
    except Exception:
        st.session_state.schedule = []

# -----------------------------
# ✅ Sidebar Navigation
# -----------------------------
with st.sidebar:
    selected = option_menu(
        "🌱 WaterWise",
        ["Dashboard", "My Fields", "My Schedule", "Ask Sprout AI", "Settings", "Help Center"],
        icons=["house", "grid", "calendar","chat", "gear", "question-circle"],
        default_index=0,
        menu_icon="psychiatry"
    )


# -----------------------------
# ✅ Normal Navigation Pages
# -----------------------------

def render_top_section(location="Paso Robles Farm", Page_Title="" ):
    date = datetime.now()
    day = date.strftime("%A")
    formatted_date = date.strftime("%B %d, %Y")

    # CSS custom
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

    # Header HTML
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

if selected == "Dashboard":
    render_top_section(Page_Title="👋 Welcome back, Christopher")
    render_dashboard()

elif selected == "Ask Sprout AI":
    render_chat()

elif selected == "My Fields":
    render_top_section(Page_Title="Fields Overview")
    render_fields()

elif selected == "My Schedule":
    render_schedule()

elif selected == "Settings":
    render_settings()

elif selected == "Help Center":
    render_help_center()