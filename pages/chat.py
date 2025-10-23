import streamlit as st
from streamlit_option_menu import option_menu
import google.generativeai as genai
import os
from datetime import datetime
from database import db


def render_chat():
    st.set_page_config(page_title="Sprout AI - Your Farming Assistant", page_icon="💬",layout="wide")
    st.title("💬 Sprout AI - Your Farming Assistant")
    st.markdown("Ask me anything about your fields, schedules, hydration, or farming tips!")

    # Lấy fields từ database
    user_fields = db.get_user_fields(st.user.email) if hasattr(st, 'user') and st.user.is_logged_in else []
    fields = user_fields if user_fields else st.session_state.get('fields', [])
    
    # Field selection dropdown
    if fields:
        selected_field = st.selectbox(
            "Select Field for Context",
            options=[field.get('name', 'Unnamed Field') for field in fields],
            index=0,
            help="Select a field to provide sensor context to the AI"
        )
        
        # Get sensor data for selected field
        field_data = next((f for f in fields if f.get('name') == selected_field), None)
    else:
        st.info("No fields found. Please add fields first.")
        field_data = None
    context = ""
    if field_data:
        context = f"Current field: {selected_field}. "
        if 'live_moisture' in field_data:
            context += f"Soil moisture: {field_data['live_moisture']}%. "
        if 'soil_temperature' in field_data:
            context += f"Soil temperature: {field_data['soil_temperature']}°C. "

    # Render past chat messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input box
    if prompt := st.chat_input("What's on your mind?"):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate AI response
        try:
            full_prompt = f"{context}{prompt}" if context else prompt
            model = genai.GenerativeModel("gemini-2.0-flash")  # ✅ Faster and stable
            response = model.generate_content(full_prompt)
            ai_response = response.text
        except Exception as e:
            ai_response = f"⚠️ Error generating response: {e}"

        # Add assistant message
        st.session_state.messages.append({"role": "assistant", "content": ai_response})
        with st.chat_message("assistant"):
            st.markdown(ai_response)

    # Clear chat button
    if st.button("🧹 Clear Chat", use_container_width=True):
        st.session_state.messages.clear()
        st.experimental_rerun()