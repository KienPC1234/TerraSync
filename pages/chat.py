import streamlit as st
from streamlit_option_menu import option_menu
import google.generativeai as genai
import os
from datetime import datetime

def render_chat():
    st.set_page_config(page_title="Sprout AI - Your Farming Assistant", page_icon="💬",layout="wide")
    st.title("💬 Sprout AI - Your Farming Assistant")
    st.markdown("Ask me anything about your fields, schedules, hydration, or farming tips!")

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
            model = genai.GenerativeModel("gemini-2.0-flash")  # ✅ Faster and stable
            response = model.generate_content(prompt)
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