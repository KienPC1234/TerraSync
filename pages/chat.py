import streamlit as st
from streamlit_option_menu import option_menu
import google.generativeai as genai
import os
from datetime import datetime , timezone
from uuid import uuid4
from database import db
from PIL import Image
import io
import base64
import logging

logger = logging.getLogger(__name__)

# ===================================================================
# --- HÀM HELPER ĐỂ LẤY DỮ LIỆU CẢM BIẾN (LIVE) ---
# ===================================================================

def get_hub_id_for_field(user_email: str, field_id: str) -> str | None:
    """Helper: Lấy hub_id được gán cho field."""
    hub = db.get("iot_hubs", {"field_id": field_id, "user_email": user_email})
    if hub:
        return hub[0].get('hub_id')
    return None

def get_latest_telemetry_stats(user_email: str, field_id: str) -> dict | None:
    """
    Lấy GÓI TIN telemetry MỚI NHẤT (không cache) để tính toán.
    """
    hub_id = get_hub_id_for_field(user_email, field_id)
    if not hub_id:
        logger.warning(f"Không tìm thấy hub cho field {field_id}")
        return None 

    telemetry_data = db.get("telemetry", {"hub_id": hub_id})
    if not telemetry_data:
        logger.warning(f"Không tìm thấy telemetry cho hub {hub_id}")
        return None
    
    try:
        latest_entry = sorted(
            telemetry_data, 
            key=lambda x: x.get('timestamp', '1970-01-01T00:00:00+00:00'), 
            reverse=True
        )[0]
    except IndexError:
        return None
        
    data = latest_entry.get("data", {})
    stats = {
        "avg_moisture": None,
        "avg_soil_temp": None,
        "air_temp": None,
        "air_humidity": None,
        "rain_intensity": 0.0,
        "timestamp": latest_entry.get('timestamp')
    }

    # Tính độ ẩm/nhiệt độ đất trung bình
    nodes = data.get("soil_nodes", [])
    if nodes:
        values_moist = [n['sensors']['soil_moisture'] for n in nodes if n.get('sensors') and 'soil_moisture' in n['sensors']]
        values_temp = [n['sensors']['soil_temperature'] for n in nodes if n.get('sensors') and 'soil_temperature' in n['sensors']]
        if values_moist:
            stats["avg_moisture"] = sum(values_moist) / len(values_moist)
        if values_temp:
            stats["avg_soil_temp"] = sum(values_temp) / len(values_temp)

    # Lấy thông số không khí
    atm_node = data.get("atmospheric_node", {})
    if atm_node.get('sensors'):
        stats["rain_intensity"] = atm_node['sensors'].get('rain_intensity', 0.0)
        stats["air_temp"] = atm_node['sensors'].get('air_temperature')
        stats["air_humidity"] = atm_node['sensors'].get('air_humidity')
        
    return stats

# ===================================================================
# --- HÀM RENDER CHAT (ĐÃ SỬA) ---
# ===================================================================

def render_chat():
    # st.set_page_config(page_title="CropNet AI - Trợ lý Nông nghiệp", page_icon="💬", layout="wide")
    
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
    

    if not hasattr(st, 'user') or not st.user.email:
        st.warning("⚠️ Vui lòng đăng nhập để sử dụng tính năng trò chuyện")
        return

    # Sidebar for chat management
    with st.sidebar:
        st.header("📱 Quản lý Trò chuyện")
        
        if st.button("📥 Lưu Cuộc trò chuyện Hiện tại"):
            if "messages" in st.session_state and st.session_state.messages:
                context = {"selected_field": st.session_state.get("selected_field")}
                
                # Sửa lỗi: Dùng db.add để lưu chat
                chat_doc = {
                    "id": str(uuid4()),
                    "user_email": st.user.email,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "messages": st.session_state.messages,
                    "context": context
                }
                if db.add("chat_history", chat_doc):
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
        # Sửa lỗi: Lấy chat history từ bảng "chat_history"
        chat_histories = db.get("chat_history", {"user_email": st.user.email})
        
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
                        # Sửa lỗi: Dùng db.delete
                        if db.delete("chat_history", {"id": chat["id"]}):
                            st.success("✅ Đã xóa cuộc trò chuyện!")
                            st.rerun()
                        else:
                            st.error("Lỗi: Không thể xóa.")
        
        # (Tính năng chia sẻ giữ nguyên)
    
    # Initialize session state for messages if not exists
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Lấy fields từ database (Sửa lỗi: dùng db.get)
    user_fields = db.get("fields", {"user_email": st.user.email}) if hasattr(st, 'user') and st.user.email else []
    fields = user_fields if user_fields else st.session_state.get('fields', [])
    
    # Field selection dropdown
    col_field, col_info = st.columns([1, 3])
    with col_field:
        if fields:
            selected_field_name = st.selectbox(
                "🌾 Chọn Vườn",
                options=[field.get('name', 'Vườn Không tên') for field in fields],
                index=0,
                help="Chọn một vườn để cung cấp ngữ cảnh cảm biến cho AI"
            )
            
            # Lấy dữ liệu tĩnh của vườn
            field_data = next((f for f in fields if f.get('name') == selected_field_name), None)
            st.session_state.selected_field = selected_field_name
        else:
            st.info("❌ Không tìm thấy vườn nào. Vui lòng thêm vườn trước.")
            field_data = None
            selected_field_name = None
    
    # --- XÂY DỰNG NGỮ CẢNH ĐỘNG (ĐÃ SỬA) ---
    context = ""
    live_stats = None
    if field_data:
        # 1. Lấy dữ liệu tĩnh từ DB
        context = f"""
--- Ngữ cảnh Vườn (Tĩnh) ---
Tên vườn: {selected_field_name}
Loại cây: {field_data.get('crop', 'N/A')}
Giai đoạn: {field_data.get('stage', 'N/A')}
Diện tích: {field_data.get('area', 0):.2f} ha
Trạng thái (đã lưu): {field_data.get('status', 'N/A')}
Tiến độ tưới (đã lưu): {field_data.get('progress', 0)}%
"""
        # 2. Lấy dữ liệu động (LIVE) từ cảm biến
        live_stats = get_latest_telemetry_stats(st.user.email, field_data.get('id'))
        
        if live_stats:
            live_context = "\n--- Ngữ cảnh Cảm biến (LIVE) ---\n"
            if live_stats.get("avg_moisture") is not None:
                live_context += f"Độ ẩm đất (TB): {live_stats['avg_moisture']:.1f}%\n"
            if live_stats.get("avg_soil_temp") is not None:
                live_context += f"Nhiệt độ đất (TB): {live_stats['avg_soil_temp']:.1f}°C\n"
            if live_stats.get("air_temp") is not None:
                live_context += f"Nhiệt độ không khí: {live_stats['air_temp']:.1f}°C\n"
            if live_stats.get("air_humidity") is not None:
                live_context += f"Độ ẩm không khí: {live_stats['air_humidity']:.1f}%\n"
            if live_stats.get("rain_intensity") is not None:
                live_context += f"Lượng mưa: {live_stats['rain_intensity']:.1f} mm/h\n"
            try:
                ts = datetime.fromisoformat(live_stats['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
                live_context += f"Thời gian cảm biến: {ts}\n"
            except: pass
            
            context += live_context
        else:
            context += "--- Ngữ cảnh Cảm biến (LIVE) ---\nKhông tìm thấy dữ liệu cảm biến (Hub/Sensor có thể đang offline).\n"
            
    # Hiển thị thông tin (Info box)
    with col_info:
        if field_data:
            if live_stats and live_stats.get("avg_moisture") is not None:
                st.info(f"🌱 {field_data.get('crop', 'N/A')} | 💧 Độ ẩm live: {live_stats['avg_moisture']:.1f}% | 🌡️ Nhiệt độ đất: {live_stats.get('avg_soil_temp', 'N/A')}°C")
            else:
                st.warning(f"🌱 {field_data.get('crop', 'N/A')} | ⚠️ Không có dữ liệu cảm biến live.")


    # System prompt (ĐÃ CẬP NHẬT)
    system_prompt = f"""
    Bạn là CropNet AI, một trợ lý nông nghiệp chuyên gia (chuyên gia nông học) của Việt Nam. Bạn giao tiếp bằng tiếng Việt.
    
    TRÁCH NHIỆM CỐT LÕI:
    1.  **Phân tích Dữ liệu Cảm biến (Ưu tiên hàng đầu):** Luôn kiểm tra "Ngữ cảnh Cảm biến (LIVE)" trước tiên. Dữ liệu này (độ ẩm, mưa, nhiệt độ) là sự thật quan trọng nhất.
    2.  **Phân tích Dữ liệu Vườn (Tĩnh):** Sử dụng "Ngữ cảnh Vườn (Tĩnh)" (loại cây, giai đoạn) để điều chỉnh lời khuyên.
    3.  **Đưa ra Lời khuyên Cụ thể:** Đừng nói chung chung. Đưa ra các bước hành động.
    
    HƯỚNG DẪN CHI TIẾT:
    -   **Khi có dữ liệu LIVE (Độ ẩm):**
        -   Nếu độ ẩm thấp (ví dụ: < 30%): Khuyến nghị tưới ngay. Đề cập đến 'progress' (tiến độ) và 'today_water' (lượng nước) của vườn.
        -   Nếu độ ẩm cao (ví dụ: > 75%): Khuyến nghị dừng tưới.
        -   Nếu có mưa (rain_intensity > 0.5 mm/h): Khuyến nghị dừng tưới ngay lập tức.
    -   **Khi phân tích ảnh (Image Analysis):**
        -   Sử dụng dữ liệu ngữ cảnh (loại cây, giai đoạn, độ ẩm) để tăng độ chính xác.
        -   Ví dụ: Nếu ảnh lá bị vàng VÀ độ ẩm thấp, có thể là do thiếu nước. Nếu ảnh lá vàng VÀ độ ẩm cao, có thể là do úng nước hoặc thiếu Nito.
    -   **Khi không có dữ liệu LIVE:** Dựa vào dữ liệu "Tĩnh" (status, progress) và lịch sử chat, nhưng phải cảnh báo user là "Tôi không có dữ liệu cảm biến mới nhất".
    -   **Định dạng:** Sử dụng Markdown, emoji (🌱💧☀️) và bảng biểu khi cần.
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
        st.image(uploaded_file, caption="Xem trước", width=100)
        if st.button("🔍 Phân tích ảnh"):
            st.session_state.analyze_image = True
            st.session_state.default_prompt = "Phân tích ảnh cây trồng này: xác định loại cây (nếu có thể), tình trạng sức khỏe, phát hiện bệnh hoặc thiếu chất. Đưa ra lời khuyên cụ thể dựa trên *dữ liệu cảm biến live* và *thông tin vườn* tôi đã cung cấp."
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
        # Quan trọng: KHÔNG gửi ngữ cảnh (context) làm một phần của tin nhắn
        # Ngữ cảnh đã được gửi trong system_prompt hoặc sẽ được thêm vào
        
        images_b64 = []
        if has_image:
            img_bytes = uploaded_file.getvalue()
            img_b64 = base64.b64encode(img_bytes).decode('utf-8')
            images_b64 = [img_b64]
            
        st.session_state.messages.append({
            "role": "user",
            "content": user_prompt, # Chỉ gửi prompt của user
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
                "gemini-2.5-flash",
                system_instruction=system_prompt, # Prompt hệ thống đã chứa ngữ cảnh tĩnh
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=0.9,
                    max_output_tokens=1024
                )
            )
            
            # Build chat history
            history = []
            for msg in st.session_state.messages[:-1]: # Lấy tất cả trừ tin nhắn cuối
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
            
            # Chuẩn bị nội dung gửi: Ngữ cảnh LIVE + Prompt + Ảnh
            current_parts = []
            # Thêm ngữ cảnh LIVE vào tin nhắn
            current_parts.append(f"**Ngữ cảnh MỚI NHẤT (LIVE SENSOR DATA):**\n{context}\n\n**Câu hỏi của tôi:**\n{user_prompt}")
            
            if has_image:
                current_img = Image.open(io.BytesIO(uploaded_file.getvalue()))
                current_parts.append(current_img)
            
            # Send the current user message with streaming
            response_stream = chat.send_message(current_parts, stream=True)
            
            # Use st.write_stream to display the response with an animation
            with st.chat_message("assistant"):
                # The st.write_stream function handles the iteration and display
                full_response = st.write_stream(response_stream)
            
            # Add the complete assistant message to history after streaming is done
            st.session_state.messages.append({"role": "assistant", "content": full_response, "images_b64": []})
            
        except Exception as e:
            ai_response = f"⚠️ Lỗi tạo phản hồi: {e}"
            st.session_state.messages.append({"role": "assistant", "content": ai_response, "images_b64": []})
            # Display error message
            with st.chat_message("assistant"):
                st.error(ai_response)
        
        # Xóa file upload sau khi xử lý
        if has_image:
            st.session_state.plant_image = None # Xóa file uploader
            st.rerun()

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

# ---
# Để chạy file này, bạn cần có file `database.py` 
# và file app chính (ví dụ `app.py`) có thể gọi `render_chat()`
# ---