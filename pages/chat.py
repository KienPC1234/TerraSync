import streamlit as st
from streamlit_option_menu import option_menu
import google.generativeai as genai
import os
from datetime import datetime
from uuid import uuid4
from database import db
from PIL import Image
import io
import base64


def render_chat():
    st.set_page_config(page_title="CropNet AI - Trợ lý Nông nghiệp", page_icon="💬", layout="wide")
    
    # Custom CSS for prettier UI
    st.markdown("""
    <style>
    .main .block-container {
        padding-top: 2rem;
    }
    .stButton > button {
        background-color: #4CAF50;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: bold;
    }
    .stButton > button:hover {
        background-color: #45a049;
    }
    .stFileUploader > div > div > div {
        border: 2px dashed #4CAF50;
        border-radius: 8px;
    }
    .stChatMessage {
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stSelectbox > div > div > select {
        border-radius: 8px;
        border: 1px solid #4CAF50;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("💬 CropNet AI - Trợ lý Nông nghiệp")
    st.markdown("🌱 Hỏi tôi bất cứ điều gì về cánh đồng, lịch trình, độ ẩm, hoặc mẹo canh tác của bạn!")
    

    if not hasattr(st, 'user') or not st.user.is_logged_in:
        st.warning("⚠️ Vui lòng đăng nhập để sử dụng tính năng trò chuyện")
        return

    # Sidebar for chat management
    with st.sidebar:
        st.header("📱 Quản lý Trò chuyện")
        
        if st.button("📥 Lưu Cuộc trò chuyện Hiện tại"):
            if "messages" in st.session_state and st.session_state.messages:
                context = {"selected_field": st.session_state.get("selected_field")}
                if db.save_chat_history(st.user.email, st.session_state.messages, context):
                    st.success("✅ Đã lưu thành công!")
                else:
                    st.error("❌ Lưu thất bại")

        if st.button("🗑️ Xóa Cuộc trò chuyện Hiện tại"):
            if "messages" in st.session_state:
                st.session_state.messages = []
            if "chat" in st.session_state:
                del st.session_state.chat
            st.success("✅ Đã xóa!")
            st.rerun()

        st.subheader("📚 Các Cuộc trò chuyện Đã lưu")
        chat_histories = db.get_user_chat_history(st.user.email)
        
        if not chat_histories:
            st.info("Chưa có cuộc trò chuyện nào được lưu.")
        
        for chat in chat_histories:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                timestamp = datetime.fromisoformat(chat["timestamp"]).strftime("%Y-%m-%d %H:%M")
                st.write(f"💭 {timestamp}")
            with col2:
                if st.button("📋 Tải", key=f"load_{chat['id']}"):
                    st.session_state.messages = chat["messages"]
                    if "chat" in st.session_state:
                        del st.session_state.chat  # Reset chat to rebuild with loaded history
                    st.rerun()
            with col3:
                if chat["user_email"] == st.user.email:  # Only owner can delete
                    if st.button("🗑️", key=f"delete_{chat['id']}"):
                        if db.delete_chat_history(chat["id"], st.user.email):
                            st.success("✅ Đã xóa cuộc trò chuyện!")
                            st.rerun()

        if st.button("🔗 Chia sẻ Cuộc trò chuyện"):
            with st.expander("Chia sẻ với email"):
                share_email = st.text_input("Nhập email người dùng để chia sẻ:")
                if share_email and st.button("Chia sẻ"):
                    current_chat = {
                        "id": str(uuid4()),
                        "messages": st.session_state.messages,
                        "context": {"selected_field": st.session_state.get("selected_field")},
                        "timestamp": datetime.now().isoformat(),
                        "user_email": st.user.email,
                        "shared_with": [share_email]
                    }
                    if db.add("chat_history", current_chat):
                        st.success(f"✅ Đã chia sẻ với {share_email}")
                    else:
                        st.error("❌ Chia sẻ thất bại")

    # Initialize session state for messages if not exists
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Lấy fields từ database
    user_fields = db.get_user_fields(st.user.email) if hasattr(st, 'user') and st.user.is_logged_in else []
    fields = user_fields if user_fields else st.session_state.get('fields', [])
    
    # Field selection dropdown
    col_field, col_info = st.columns([1, 3])
    with col_field:
        if fields:
            selected_field = st.selectbox(
                "🌾 Chọn Cánh đồng",
                options=[field.get('name', 'Cánh đồng Không tên') for field in fields],
                index=0,
                help="Chọn một cánh đồng để cung cấp ngữ cảnh cảm biến cho AI"
            )
            
            # Get sensor data for selected field
            field_data = next((f for f in fields if f.get('name') == selected_field), None)
            st.session_state.selected_field = selected_field
        else:
            st.info("❌ Không tìm thấy cánh đồng nào. Vui lòng thêm cánh đồng trước.")
            field_data = None
            selected_field = None
    
    # Display field info if available
    with col_info:
        if field_data:
            st.info(f"🌱 Cây trồng: {field_data.get('crop', 'N/A')} | Giai đoạn: {field_data.get('stage', 'N/A')}")
    
    # Build dynamic context based on selected field
    context = ""
    if field_data:
        context = f"Cánh đồng hiện tại: {selected_field}. "
        if 'live_moisture' in field_data:
            context += f"Độ ẩm đất: {field_data['live_moisture']}%. "
        if 'soil_temperature' in field_data:
            context += f"Nhiệt độ đất: {field_data['soil_temperature']}°C. "
        if 'crop' in field_data:
            context += f"Loại cây: {field_data['crop']}. "
        if 'stage' in field_data:
            context += f"Giai đoạn sinh trưởng: {field_data['stage']}. "
        if 'area' in field_data:
            context += f"Diện tích: {field_data['area']:.2f} ha. "

    # System prompt
    system_prompt = """
    Bạn là CropNet AI, một trợ lý nông nghiệp chuyên gia về nông nghiệp chính xác, quản lý tưới tiêu, sức khỏe cây trồng và thực hành nông nghiệp bền vững. 
    Bạn am hiểu về các loại cây trồng khác nhau (ví dụ: lúa, ngô, lúa mì, đậu nành, rau củ), khoa học đất, tác động thời tiết, quản lý sâu bệnh, và các khuyến nghị dựa trên dữ liệu.
    
    Hướng dẫn chính:
    - Luôn hữu ích, ngắn gọn và có hành động. Sử dụng dấu đầu dòng cho danh sách, bảng cho so sánh, và emoji để nhấn mạnh (ví dụ: 🌱 cho cây trồng, 💧 cho nước).
    - Dựa phản hồi vào ngữ cảnh được cung cấp (dữ liệu cánh đồng như độ ẩm, nhiệt độ, loại cây) và lịch sử trò chuyện.
    - Nếu có ngữ cảnh, điều chỉnh lời khuyên cho cánh đồng cụ thể (ví dụ: "Đối với cánh đồng lúa của bạn với độ ẩm 75%...").
    - Đề xuất các bước thực tế, tính toán (ví dụ: ETc cho nhu cầu tưới), hoặc tích hợp (ví dụ: "Kiểm tra lịch tưới của bạn").
    - Nếu không có ngữ cảnh, hỏi câu hỏi làm rõ lịch sự.
    - Kết thúc bằng một câu hỏi để tiếp tục trò chuyện nếu phù hợp.
    - Phản hồi bằng tiếng Việt nếu người dùng hỏi bằng tiếng Việt; nếu không, sử dụng tiếng Anh.
    
    Lịch sử trò chuyện: Sử dụng để nhớ các cuộc thảo luận trước và xây dựng trên chúng (ví dụ: tham chiếu lời khuyên trước).
    """

    # Render past chat messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            for img_b64 in msg.get("images_b64", []):
                img_data = base64.b64decode(img_b64)
                st.image(io.BytesIO(img_data), width=200, caption="Ảnh cây trồng")
            st.markdown(msg["content"])

    st.subheader("📷 Tải ảnh lên")
    uploaded_file = st.file_uploader(
        "Chọn ảnh cây trồng",
        type=["png", "jpg", "jpeg"],
        key="plant_image",
        help="Tải ảnh cây trồng để AI phân tích sức khỏe và vấn đề."
    )
    if uploaded_file:
        # Preview the image
        st.image(uploaded_file, caption="Xem trước", width=100)
        if st.button("🔍 Phân tích ảnh"):
            st.session_state.analyze_image = True
            st.session_state.default_prompt = "Phân tích ảnh cây trồng này: xác định loại cây, tình trạng sức khỏe, phát hiện vấn đề nếu có, và đưa ra lời khuyên cụ thể dựa trên dữ liệu cánh đồng."
            st.rerun()
    st.subheader("💬 Trò chuyện")
    prompt = st.chat_input("Hỏi về nông nghiệp...")

    # Process user input
    user_prompt = None
    has_image = False
    if prompt:
        user_prompt = prompt
        has_image = uploaded_file is not None
    elif "analyze_image" in st.session_state and "default_prompt" in st.session_state:
        user_prompt = st.session_state.default_prompt
        del st.session_state.analyze_image
        del st.session_state.default_prompt
        has_image = uploaded_file is not None

    if user_prompt:
        user_message_with_context = f"{context}{user_prompt}" if context else user_prompt
        # Add user message
        images_b64 = []
        if has_image:
            img_bytes = uploaded_file.getvalue()
            img_b64 = base64.b64encode(img_bytes).decode('utf-8')
            images_b64 = [img_b64]
        st.session_state.messages.append({
            "role": "user",
            "content": user_prompt,
            "images_b64": images_b64
        })
        with st.chat_message("user"):
            if has_image:
                st.image(uploaded_file, caption="Ảnh cây trồng", width=200)
            st.markdown(user_prompt)

        # Generate AI response using chat history
        try:
            # Configure Gemini model
            model = genai.GenerativeModel(
                "gemini-2.5-flash",  # Multimodal-capable model
                system_instruction=system_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=0.9,
                    max_output_tokens=1024
                )
            )
            
            # Build chat history from session state (exclude the latest user message)
            history = []
            for msg in st.session_state.messages[:-1]:
                role = msg["role"]
                parts = [msg["content"]]
                for img_b64 in msg.get("images_b64", []):
                    img_data = base64.b64decode(img_b64)
                    img = Image.open(io.BytesIO(img_data))
                    parts.append(img)
                history.append({"role": role, "parts": parts})
            
            # Start or continue chat session
            if "chat" not in st.session_state:
                chat = model.start_chat(history=history)
                st.session_state.chat = chat
            else:
                chat = st.session_state.chat
            
            # Prepare current parts
            current_parts = [user_message_with_context]
            if has_image:
                current_img = Image.open(io.BytesIO(uploaded_file.getvalue()))
                current_parts.append(current_img)
            
            # Send the current user message
            response = chat.send_message(current_parts)
            ai_response = response.text
            
            # Add assistant message to history
            st.session_state.messages.append({"role": "assistant", "content": ai_response, "images_b64": []})
            
        except Exception as e:
            ai_response = f"⚠️ Lỗi tạo phản hồi: {e}"
            st.session_state.messages.append({"role": "assistant", "content": ai_response, "images_b64": []})

        # Display AI response
        with st.chat_message("assistant"):
            st.markdown(ai_response)

    # Clear chat button at the bottom
    col_clear, _ = st.columns([1, 4])
    with col_clear:
        if st.button("🧹 Xóa Toàn bộ Chat"):
            st.session_state.messages = []
            if "chat" in st.session_state:
                del st.session_state.chat
            if "analyze_image" in st.session_state:
                del st.session_state.analyze_image
            if "default_prompt" in st.session_state:
                del st.session_state.default_prompt
            st.rerun()