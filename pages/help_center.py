import streamlit as st
import google.generativeai as genai
import os
from database import db
from datetime import datetime


def render_help_center():
    st.title("🆘 Trung tâm Trợ giúp & Hỗ trợ")
    st.markdown(
        "Nhận trợ giúp về TerraSync IoT và tìm câu trả lời cho các câu hỏi "
        "thường gặp")

    tabs_list = ["💬 Trợ lý AI", "📚 Tài liệu", "🔧 Xử lý sự cố", "📞 Liên hệ Hỗ trợ"]
    tabs = st.tabs(tabs_list)

    with tabs[0]:
        render_ai_assistant()
    with tabs[1]:
        render_documentation()
    with tabs[2]:
        render_troubleshooting()
    with tabs[3]:
        render_contact_support()


def render_ai_assistant():
    st.subheader("🤖 Trợ lý AI TerraSync")
    st.markdown(
        "Hỏi tôi bất cứ điều gì về TerraSync IoT, nông nghiệp hoặc các câu "
        "hỏi kỹ thuật!")

    user_fields = db.get(
        "fields", {
            "user_email": st.user.email}) if hasattr(
        st, 'user') and st.user.is_logged_in else []
    user_hubs = db.get(
        "iot_hubs", {
            "user_email": st.user.email}) if hasattr(
        st, 'user') and st.user.is_logged_in else []

    context_info = f"""
    Người dùng có {len(user_fields)} vườn và {len(user_hubs)} hub IoT.
    Các vườn: {[f.get('name', 'Không tên') for f in user_fields[:3]]}
    """

    api_key = os.getenv("GEMINI_API_KEY") or st.secrets.get(
        "gemini", {}).get("api_key", "")
    if not api_key:
        st.error(
            "⚠️ Khóa API Gemini chưa được định cấu hình. Vui lòng kiểm tra "
            "tệp secrets.toml của bạn.")
        return

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    if 'help_messages' not in st.session_state:
        st.session_state.help_messages = []

    for message in st.session_state.help_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Hỏi một câu về TerraSync...")
    if prompt:
        st.session_state.help_messages.append(
            {"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("🤖 AI đang suy nghĩ..."):
                try:
                    full_prompt = f"""
                    Bạn là Trợ lý AI của TerraSync, một AI hữu ích cho nông
                    nghiệp thông minh và IoT nông nghiệp.

                    Bối cảnh người dùng: {context_info}

                    Câu hỏi của người dùng: {prompt}

                    Vui lòng cung cấp thông tin hữu ích, chính xác về:
                    - Các tính năng và cách sử dụng TerraSync IoT
                    - Kỹ thuật canh tác thông minh
                    - Quản lý thiết bị IoT
                    - Tối ưu hóa tưới tiêu
                    - Chẩn đoán bệnh cây trồng
                    - Theo dõi thời tiết
                    - Lời khuyên nông nghiệp chung

                    Hãy thân thiện, cung cấp thông tin và cụ thể theo bối cảnh
                    của người dùng khi có thể.
                    """

                    response = model.generate_content(full_prompt)
                    ai_response = response.text

                    st.session_state.help_messages.append(
                        {"role": "assistant", "content": ai_response})
                    st.markdown(ai_response)

                except Exception as e:
                    error_msg = f"Xin lỗi, tôi đã gặp lỗi: {str(e)}"
                    st.session_state.help_messages.append(
                        {"role": "assistant", "content": error_msg})
                    st.error(error_msg)

    st.subheader("🚀 Hành động nhanh")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📖 Cách thêm vườn?"):
            st.session_state.help_messages.append(
                {"role": "user", "content": "Làm cách nào để thêm một vườn "
                 "mới vào TerraSync?"})
            st.rerun()

    with col2:
        if st.button("🔧 Trợ giúp cài đặt IoT"):
            st.session_state.help_messages.append(
                {"role": "user", "content": "Làm cách nào để thiết lập các "
                 "thiết bị IoT?"})
            st.rerun()

    with col3:
        if st.button("💧 Mẹo tưới tiêu"):
            st.session_state.help_messages.append(
                {"role": "user", "content": "Một số mẹo tối ưu hóa tưới "
                 "tiêu là gì?"})
            st.rerun()


def render_documentation():
    st.subheader("📚 Tài liệu & Hướng dẫn")

    with st.expander("🚀 Bắt đầu", expanded=True):
        st.markdown("""
        ### Chào mừng đến với TerraSync IoT!

        **Bước 1: Thêm vườn của bạn**
        - Tới trang "Vườn của tôi"
        - Nhấn "Thêm vườn mới"
        - Chọn từ phát hiện AI, tọa độ thủ công hoặc vẽ trên bản đồ

        **Bước 2: Thiết lập thiết bị IoT**
        - Tới trang "Quản lý IoT"
        - Đăng ký hub IoT của bạn
        - Kết nối cảm biến để theo dõi vườn của bạn

        **Bước 3: Tạo lịch tưới**
        - Tới trang "Lịch trình của tôi"
        - Chọn vườn của bạn
        - Tạo lịch tưới được tối ưu hóa

        **Bước 4: Theo dõi bằng AI**
        - Sử dụng "Phát hiện AI" để chẩn đoán bệnh cây trồng
        - Kiểm tra "Chế độ xem vệ tinh" để theo dõi vườn
        - Trò chuyện với CropNet AI để nhận lời khuyên cá nhân hóa
        """)

    with st.expander("🔧 Hướng dẫn tính năng"):
        st.markdown("""
        ### Phát hiện vườn bằng AI
        - Tải lên hình ảnh vệ tinh hoặc từ trên không
        - AI tự động phát hiện ranh giới vườn
        - Gợi ý loại cây trồng và tính toán diện tích

        ### Quản lý IoT
        - Kết nối Raspberry Pi 4 làm hub
        - Theo dõi độ ẩm đất, nhiệt độ, độ ẩm không khí
        - Giao tiếp RF 433MHz với phạm vi lên đến 1km

        ### Tối ưu hóa tưới tiêu
        - Lập lịch dựa trên thời tiết
        - Yêu cầu nước cụ thể theo cây trồng
        - Theo dõi và đề xuất hiệu quả

        ### Chẩn đoán bệnh cây trồng
        - Tải lên hình ảnh lá để AI phân tích
        - Nhận dạng bệnh và gợi ý điều trị
        - Mẹo phòng ngừa và theo dõi
        """)

    with st.expander("🔌 Tài liệu API"):
        st.markdown("""
        ### Ghi nhận dữ liệu IoT
        ```
        POST /api/v1/data/ingest
        Content-Type: application/json

        {
          "hub_id": "your-hub-id",
          "timestamp": "2025-01-15T10:00:00Z",
          "location": {"lat": 20.45, "lon": 106.32},
          "data": {
            "soil_nodes": [...],
            "atmospheric_node": {...}
          }
        }
        ```

        ### API Thời tiết
        - Tích hợp Open-Meteo cho dữ liệu thời tiết
        - Dự báo 7 ngày với lượng mưa, nhiệt độ, gió
        - Đánh giá rủi ro và khuyến nghị tưới tiêu

        ### Dữ liệu vệ tinh
        - OpenET (NASA) cho thoát hơi nước
        - Phân tích NDVI cho sức khỏe thực vật
        - Loại bỏ mây và tăng cường hình ảnh
        """)


def render_troubleshooting():
    st.subheader("🔧 Hướng dẫn xử lý sự cố")

    st.markdown("### Các vấn đề thường gặp & Giải pháp")

    issue_categories = {
        "🔐 Xác thực": [
            "**Vấn đề**: Không thể đăng nhập bằng Google",
            "**Giải pháp**: Kiểm tra tệp secrets.toml của bạn có thông tin "
            "xác thực Google OAuth chính xác không",
            "**Vấn đề**: Dữ liệu người dùng không lưu",
            "**Giải pháp**: Đảm bảo tệp cơ sở dữ liệu có quyền ghi"
        ],
        "📡 Kết nối IoT": [
            "**Vấn đề**: Hub IoT không kết nối",
            "**Giải pháp**: Kiểm tra kết nối mạng và địa chỉ IP của hub",
            "**Vấn đề**: Cảm biến không phản hồi",
            "**Giải pháp**: Xác minh giao tiếp RF và mức pin"
        ],
        "🗺️ Quản lý vườn": [
            "**Vấn đề**: Không thể thêm vườn",
            "**Giải pháp**: Đảm bảo bạn đã đăng nhập và có tọa độ hợp lệ",
            "**Vấn đề**: Phát hiện AI không hoạt động",
            "**Giải pháp**: Kiểm tra chất lượng hình ảnh và định dạng tệp "
            "(JPG/PNG)"
        ],
        "💧 Tưới tiêu": [
            "**Vấn đề**: Lịch trình không tạo được",
            "**Giải pháp**: Xác minh dữ liệu vườn và kết nối API thời tiết",
            "**Vấn đề**: Tính toán nước không chính xác",
            "**Giải pháp**: Kiểm tra cài đặt hệ số cây trồng và hiệu quả tưới"
        ]
    }

    for category, issues in issue_categories.items():
        with st.expander(category):
            for issue in issues:
                st.markdown(issue)

    st.subheader("🔍 Kiểm tra trạng thái hệ thống")

    if st.button("🔍 Chạy kiểm tra hệ thống"):
        with st.spinner("Đang kiểm tra trạng thái hệ thống..."):
            try:
                db.tables()
                st.success("✅ Cơ sở dữ liệu: Đã kết nối")
            except Exception as e:
                st.error(f"❌ Cơ sở dữ liệu: Lỗi - {str(e)}")

            api_key = st.secrets.get("gemini", {}).get("api_key", "")
            if api_key:
                st.success("✅ API Gemini: Đã định cấu hình")
            else:
                st.warning("⚠️ API Gemini: Chưa được định cấu hình")

            if hasattr(st, 'user') and st.user.is_logged_in:
                user_fields = db.get("fields", {"user_email": st.user.email})
                st.success(
                    f"✅ Dữ liệu người dùng: Tìm thấy {len(user_fields)} vườn")
            else:
                st.warning("⚠️ Dữ liệu người dùng: Chưa đăng nhập")

    st.subheader("📋 Thông tin gỡ lỗi")

    if st.button("📋 Hiển thị thông tin gỡ lỗi"):
        debug_info = {
            "Email người dùng": st.user.email if hasattr(
                st,
                'user') and st.user.is_logged_in else "Chưa đăng nhập",
            "Bảng cơ sở dữ liệu": db.tables(),
            "Khóa trạng thái phiên": list(
                st.session_state.keys()),
            "Phiên bản Streamlit": st.__version__}

        for key, value in debug_info.items():
            st.write(f"**{key}**: {value}")


def render_contact_support():
    st.subheader("📞 Liên hệ Hỗ trợ")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        ### 📧 Hỗ trợ qua Email
        **Hỗ trợ chung**: support@terrasync.io
        **Vấn đề kỹ thuật**: tech@terrasync.io
        **Yêu cầu kinh doanh**: business@terrasync.io

        ### 📱 Hỗ trợ qua điện thoại
        **Hotline**: +84 0978 589 220
        **Giờ làm việc**: Thứ Hai - Thứ Sáu 8AM-6PM (GMT+7)
        """)

    with col2:
        st.markdown("""
        ### 💬 Trò chuyện trực tiếp
        Có sẵn trong giờ làm việc
        Thời gian phản hồi trung bình: 5 phút

        ### 🐛 Báo cáo lỗi
        **GitHub Issues**:
        [github.com/terrasync/issues](https://github.com/terrasync/issues)
        **Ưu tiên**: Lỗi nghiêm trọng được phản hồi trong 24 giờ
        """)

    st.subheader("📝 Gửi tin nhắn")

    with st.form("contact_form"):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input(
                "Tên của bạn",
                value=st.user.name if hasattr(
                    st,
                    'user') and st.user.is_logged_in else "")
            email = st.text_input(
                "Email",
                value=st.user.email if hasattr(
                    st,
                    'user') and st.user.is_logged_in else "")

        with col2:
            issue_type = st.selectbox("Loại vấn đề", [
                "Câu hỏi chung",
                "Vấn đề kỹ thuật",
                "Yêu cầu tính năng",
                "Báo cáo lỗi",
                "Vấn đề tài khoản"
            ])
            priority = st.selectbox(
                "Mức độ ưu tiên", [
                    "Thấp", "Trung bình", "Cao", "Nghiêm trọng"])

        subject = st.text_input("Chủ đề")
        message = st.text_area("Tin nhắn", height=150)

        if st.form_submit_button("📤 Gửi tin nhắn", type="primary"):
            if not message:
                st.error("Vui lòng nhập tin nhắn")
            else:
                st.success(
                    "✅ Gửi tin nhắn thành công! Chúng tôi sẽ liên hệ lại với "
                    "bạn trong vòng 24 giờ.")

                contact_data = {
                    "name": name,
                    "email": email,
                    "issue_type": issue_type,
                    "priority": priority,
                    "subject": subject,
                    "message": message,
                    "user_email": st.user.email if hasattr(
                        st,
                        'user') and st.user.is_logged_in else None,
                    "timestamp": datetime.now().isoformat()}

                db.add("support_messages", contact_data)

    st.subheader("❓ Câu hỏi thường gặp")

    faqs = [
        {"Q": "Làm cách nào để kết nối các thiết bị IoT của tôi?",
         "A": "Tới Quản lý IoT → Thêm Hub mới → Nhập chi tiết hub và "
         "kết nối cảm biến"},
        {"Q": "Tôi có thể sử dụng TerraSync mà không cần thiết bị IoT không?",
         "A": "Có! Bạn có thể sử dụng nhập dữ liệu thủ công và lập lịch "
         "dựa trên thời tiết"},
        {"Q": "Phát hiện bệnh bằng AI có chính xác không?",
         "A": "AI của chúng tôi đạt độ chính xác 85-90% đối với các bệnh "
         "cây trồng phổ biến với hình ảnh rõ nét"},
        {"Q": "Những loại cây trồng nào được hỗ trợ?",
         "A": "Lúa, Ngô, Lúa mì, Đậu nành, Cà chua, Khoai tây, Bắp cải và "
         "các loại cây trồng tùy chỉnh"},
        {"Q": "Tôi có thể tiết kiệm được bao nhiêu nước?",
         "A": "Người dùng thường tiết kiệm 20-40% nước thông qua lịch tưới "
         "được tối ưu hóa"}
    ]

    for faq in faqs:
        with st.expander(faq["Q"]):
            st.write(faq["A"])