import streamlit as st
from streamlit_option_menu import option_menu
import google.generativeai as genai
import os
from datetime import datetime
from uuid import uuid4
from database import db


def render_chat():
    st.set_page_config(page_title="Sprout AI - Your Farming Assistant", page_icon="💬", layout="wide")
    st.title("💬 Sprout AI - Your Farming Assistant")
    st.markdown("Ask me anything about your fields, schedules, hydration, or farming tips!")

    if not hasattr(st, 'user') or not st.user.is_logged_in:
        st.warning("Please login to use the chat feature")
        return

    # Chat History Management
    if st.sidebar.button("📥 Save Current Chat"):
        if "messages" in st.session_state and st.session_state.messages:
            context = {"selected_field": st.session_state.get("selected_field")}
            if db.save_chat_history(st.user.email, st.session_state.messages, context):
                st.sidebar.success("Chat saved successfully!")
            else:
                st.sidebar.error("Failed to save chat")

    if st.sidebar.button("🗑️ Clear Current Chat"):
        if "messages" in st.session_state:
            st.session_state.messages = []
            st.sidebar.success("Chat cleared!")

    # Show saved chats
    st.sidebar.markdown("---")
    st.sidebar.subheader("📚 Saved Chats")
    chat_histories = db.get_user_chat_history(st.user.email)
    
    for chat in chat_histories:
        col1, col2, col3 = st.sidebar.columns([2, 1, 1])
        with col1:
            timestamp = datetime.fromisoformat(chat["timestamp"]).strftime("%Y-%m-%d %H:%M")
            st.write(f"💭 {timestamp}")
        with col2:
            if st.button("📋 Load", key=f"load_{chat['id']}"):
                st.session_state.messages = chat["messages"]
                st.rerun()
        with col3:
            if chat["user_email"] == st.user.email:  # Only owner can delete/share
                if st.button("🗑️", key=f"delete_{chat['id']}"):
                    if db.delete_chat_history(chat["id"], st.user.email):
                        st.sidebar.success("Chat deleted!")
                        st.rerun()

    # Share chat modal
    if st.sidebar.button("🔗 Share Chat"):
        share_email = st.sidebar.text_input("Enter user email to share with:")
        if share_email and st.sidebar.button("Share"):
            current_chat = {
                "id": str(uuid4()),
                "messages": st.session_state.messages,
                "context": {"selected_field": st.session_state.get("selected_field")},
                "timestamp": datetime.now().isoformat(),
                "user_email": st.user.email,
                "shared_with": [share_email]
            }
            if db.add("chat_history", current_chat):
                st.sidebar.success(f"Chat shared with {share_email}")
            else:
                st.sidebar.error("Failed to share chat")

    # Initialize session state for messages if not exists
    if "messages" not in st.session_state:
        st.session_state.messages = []

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
    
    # Build dynamic context based on selected field
    context = ""
    if field_data:
        context = f"Current field: {selected_field}. "
        if 'live_moisture' in field_data:
            context += f"Soil moisture: {field_data['live_moisture']}%. "
        if 'soil_temperature' in field_data:
            context += f"Soil temperature: {field_data['soil_temperature']}°C. "
        if 'crop' in field_data:
            context += f"Crop type: {field_data['crop']}. "
        if 'stage' in field_data:
            context += f"Growth stage: {field_data['stage']}. "
        if 'area' in field_data:
            context += f"Area: {field_data['area']:.2f} ha. "

    # System prompt to make AI more intelligent and specialized
    system_prompt = """
    You are Sprout AI, an expert farming assistant specialized in precision agriculture, irrigation management, crop health, and sustainable farming practices. 
    You are knowledgeable about various crops (e.g., rice, corn, wheat, soybeans, vegetables), soil science, weather impacts, pest management, and data-driven recommendations.
    
    Key guidelines:
    - Always be helpful, concise, and actionable. Use bullet points for lists, tables for comparisons, and emojis for emphasis (e.g., 🌱 for crops, 💧 for water).
    - Base responses on the provided context (field data like moisture, temperature, crop type) and conversation history.
    - If context is given, tailor advice to the specific field (e.g., "For your rice field at 75% moisture...").
    - Suggest practical steps, calculations (e.g., ETc for irrigation needs), or integrations (e.g., "Check your schedule for watering").
    - If no context, ask clarifying questions politely.
    - End with a question to continue the conversation if appropriate.
    - Respond in Vietnamese if the user asks in Vietnamese; otherwise, use English.
    
    Conversation history: Use this to remember previous discussions and build on them (e.g., reference past advice).
    """

    # Render past chat messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input box
    if prompt := st.chat_input("What's on your mind?"):
        # Add user message with context
        user_message_with_context = f"{context}{prompt}" if context else prompt
        st.session_state.messages.append({"role": "user", "content": user_message_with_context})
        with st.chat_message("user"):
            st.markdown(prompt)  # Display only the raw prompt, not context

        # Generate AI response using chat history
        try:
            # Configure Gemini model
            model = genai.GenerativeModel(
                "gemini-2.0-flash",
                system_instruction=system_prompt,  # Use system prompt for consistent behavior
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,  # Balanced creativity
                    top_p=0.9,
                    max_output_tokens=1024
                )
            )
            
            # Build chat history from session state (exclude the latest user message for now)
            history = []
            for msg in st.session_state.messages[:-1]:  # Up to previous messages
                history.append(msg)
            
            # Start or continue chat session
            if "chat" not in st.session_state:
                chat = model.start_chat(history=[{"role": msg["role"], "parts": [msg["content"]]} for msg in history])
                st.session_state.chat = chat
            else:
                chat = st.session_state.chat
            
            # Send the current user message
            response = chat.send_message(user_message_with_context)
            ai_response = response.text
            
            # Add assistant message to history
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
            
        except Exception as e:
            ai_response = f"⚠️ Error generating response: {e}"
            st.session_state.messages.append({"role": "assistant", "content": ai_response})

        # Display AI response
        with st.chat_message("assistant"):
            st.markdown(ai_response)

    # Clear chat button
    if st.button("🧹 Clear Chat", use_container_width=True):
        st.session_state.messages = []
        if "chat" in st.session_state:
            del st.session_state.chat
        st.rerun()