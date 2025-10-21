# pages/help_center.py - Chat Focused
import streamlit as st
import google.generativeai as genai
import os

def render_help_center():
    st.header("Help Center")

    # AI Chat - Clean Chat Interface
    api_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("gemini", {}).get("api_key", "AIzaSyAd411kiJdkeHpSu2xhdb_fNzmxFzkeco0")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')

    if 'messages' not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask a question...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        response = model.generate_content(prompt)
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        with st.chat_message("assistant"):
            st.markdown(response.text)

    # Resources - Simple Links
    st.subheader("Resources")
    st.write("[User Guide](https://streamlit.io)")
    st.write("[Support](https://streamlit.io)")