import streamlit as st
from database import db, crop_db
from datetime import datetime
import json


def render_settings():
    st.title("⚙️ Cài đặt & Cấu hình")
    st.markdown("Quản lý tài khoản TerraSync IoT và cài đặt ứng dụng của bạn")

    tabs_list = ["👤 Hồ sơ", "🌍 Vị trí", "🔧 Tùy chọn", "🔐 Bảo mật"]
    if st.session_state.get("is_admin"):
        tabs_list.append("👑 Bảng điều khiển quản trị")

    tabs = st.tabs(tabs_list)

    with tabs[0]:
        render_profile_settings()
    with tabs[1]:
        render_location_settings()
    with tabs[2]:
        render_preferences()
    with tabs[3]:
        render_security_settings()

    if st.session_state.get("is_admin") and len(tabs) > 4:
        with tabs[4]:
            render_admin_panel()


def render_admin_panel():
    st.subheader("👑 Bảng điều khiển quản trị")
    st.write(
        "Chào mừng đến với bảng điều khiển quản trị. "
        "Tại đây bạn có thể quản lý người dùng và các loại cây trồng.")

    admin_tab1, admin_tab2 = st.tabs(
        ["👤 Quản lý người dùng", "🌱 Quản lý cây trồng"])

    with admin_tab1:
        render_user_management()
    with admin_tab2:
        render_crop_management()


def render_user_management():
    st.subheader("Quản lý người dùng")

    with st.expander("Thêm người dùng mới"):
        with st.form("new_user_form"):
            email = st.text_input("Email")
            name = st.text_input("Tên")
            password = st.text_input("Mật khẩu", type="password")
            is_admin = st.checkbox("Là quản trị viên")

            if st.form_submit_button("Thêm người dùng"):
                db.add("users", {"email": email, "name": name,
                                  "password": password, "is_admin": is_admin})
                st.success(f"Người dùng {name} đã được thêm thành công.")
                st.rerun()

    users = db.get("users")
    st.write(f"Tổng số người dùng: {len(users)}")

    for user in users:
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            st.write(user.get("name"))
            st.caption(user.get("email"))
        with col2:
            if st.button("Xóa", key=f"delete_user_{user.get('id')}"):
                db.delete("users", {"id": user.get("id")})
                st.rerun()


def render_crop_management():
    st.subheader("Quản lý cây trồng")

    with st.expander("Thêm cây trồng mới"):
        with st.form("new_crop_form"):
            name = st.text_input("Tên cây trồng")
            call_name = st.text_input("Tên gọi (ví dụ: 'tomato')")

            st.write("Nhu cầu nước (giá trị Kc cho mỗi giai đoạn)")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                initial = st.number_input("Ban đầu", value=0.6)
            with col2:
                development = st.number_input("Phát triển", value=0.8)
            with col3:
                mid_season = st.number_input("Giữa mùa", value=1.0)
            with col4:
                late_season = st.number_input("Cuối mùa", value=0.7)

            st.write("Giai đoạn sinh trưởng (số ngày cho mỗi giai đoạn)")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                gs_initial = st.number_input("Ban đầu (ngày)", value=20)
            with col2:
                gs_development = st.number_input("Phát triển (ngày)", value=30)
            with col3:
                gs_mid_season = st.number_input("Giữa mùa (ngày)", value=30)
            with col4:
                gs_late_season = st.number_input("Cuối mùa (ngày)", value=20)

            if st.form_submit_button("Thêm cây trồng"):
                new_crop = {
                    "name": name,
                    "call_name": call_name,
                    "water_needs": {
                        "initial": initial,
                        "development": development,
                        "mid_season": mid_season,
                        "late_season": late_season},
                    "growth_stages": {
                        "initial": gs_initial,
                        "development": gs_development,
                        "mid_season": gs_mid_season,
                        "late_season": gs_late_season},
                    "warnings": {
                        "nhiet_do": {
                            "min": 10,
                            "max": 35},
                        "do_am": {
                            "min": 60,
                            "max": 80}},
                }
                crops = crop_db.get("crops")
                crops.append(new_crop)
                crop_db.overwrite_table("crops", crops)
                st.success(f"Cây trồng {name} đã được thêm thành công.")
                st.rerun()

    crops = crop_db.get("crops")
    st.write(f"Tổng số cây trồng: {len(crops)}")

    for crop in crops:
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            st.write(crop.get("name"))
        with col2:
            if st.button("Xóa", key=f"delete_crop_{crop.get('name')}"):
                updated_crops = [
                    c for c in crops if c.get("name") != crop.get("name")]
                crop_db.overwrite_table("crops", updated_crops)
                st.rerun()


def render_profile_settings():
    st.subheader("👤 Cài đặt hồ sơ")

    if hasattr(st, 'user') and st.user.is_logged_in:
        user_data = db.get("users", {"email": st.user.email})
        user_data = user_data[0] if user_data else {}

        with st.form("profile_form"):
            col1, col2 = st.columns(2)

            with col1:
                name = st.text_input(
                    "Họ và tên",
                    value=user_data.get('name', '') or st.user.name or '')
                st.text_input(
                    "Email", value=st.user.email, disabled=True)
                phone = st.text_input(
                    "Số điện thoại", value=user_data.get('phone', ''))

            with col2:
                organization = st.text_input(
                    "Tên trang trại", value=user_data.get('organization', ''))
                role = st.selectbox(
                    "Vai trò", [
                        "Nông dân", "Quản lý trang trại", "Kỹ sư nông nghiệp",
                        "Nhà nghiên cứu", "Khác"])
                experience = st.selectbox(
                    "Kinh nghiệm canh tác", [
                        "Người mới bắt đầu (< 1 năm)", "Trung cấp (1-5 năm)",
                        "Nâng cao (5-10 năm)", "Chuyên gia (10+ năm)"])

            bio = st.text_area(
                "Tiểu sử/Mô tả",
                value=user_data.get(
                    'bio',
                    ''),
                height=100)

            if st.form_submit_button("💾 Lưu hồ sơ", type="primary"):
                update_data = {
                    'name': name,
                    'phone': phone,
                    'organization': organization,
                    'role': role,
                    'experience': experience,
                    'bio': bio,
                    'updated_at': datetime.now().isoformat()}

                if user_data:
                    db.update("users", {"email": st.user.email}, update_data)
                else:
                    user_data = {
                        **update_data,
                        'email': st.user.email,
                        'first_login': datetime.now().isoformat(),
                        'last_login': datetime.now().isoformat()}
                    db.add("users", user_data)

                st.success("✅ Cập nhật hồ sơ thành công!")
                st.rerun()
    else:
        st.warning("Vui lòng đăng nhập để truy cập cài đặt hồ sơ")


def render_location_settings():
    st.subheader("🌍 Cài đặt vị trí & trang trại")

    user_data = db.get("users", {"email": st.user.email}) if hasattr(
        st, 'user') and st.user.is_logged_in else None
    user_data = user_data[0] if user_data else {}
    default_location = user_data.get(
        'default_location', {
            "lat": 20.450123, "lon": 106.325678})

    with st.form("location_form"):
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Vị trí trang trại mặc định**")
            lat = st.number_input(
                "Vĩ độ",
                value=default_location.get('lat', 20.450123),
                format="%.6f")
            lon = st.number_input(
                "Kinh độ",
                value=default_location.get('lon', 106.325678),
                format="%.6f")
            timezone = st.selectbox(
                "Múi giờ",
                ["Asia/Ho_Chi_Minh", "UTC", "America/New_York", "Europe/London"])

        with col2:
            st.write("**Cài đặt khu vực**")
            country = st.selectbox(
                "Quốc gia",
                ["Việt Nam", "Hoa Kỳ", "Ấn Độ", "Trung Quốc", "Brazil", "Khác"])
            language = st.selectbox(
                "Ngôn ngữ", [
                    "Tiếng Việt", "Tiếng Anh", "Tiếng Trung",
                    "Tiếng Tây Ban Nha", "Tiếng Bồ Đào Nha"])
            units = st.selectbox(
                "Đơn vị đo lường", [
                    "Hệ mét (m, kg, °C)",
                    "Hệ đo lường Anh (ft, lb, °F)"])

        if st.form_submit_button("💾 Lưu cài đặt vị trí", type="primary"):
            location_data = {
                'default_location': {
                    "lat": lat,
                    "lon": lon},
                'timezone': timezone,
                'country': country,
                'language': language,
                'units': units,
                'updated_at': datetime.now().isoformat()}

            if user_data:
                db.update("users", {"email": st.user.email}, location_data)
            else:
                user_data = {
                    **location_data,
                    'email': st.user.email,
                    'first_login': datetime.now().isoformat(),
                    'last_login': datetime.now().isoformat()}
                db.add("users", user_data)

            st.success("✅ Đã lưu cài đặt vị trí!")
            st.rerun()

    if 'lat' in locals() and 'lon' in locals() and lat and lon:
        import folium
        from streamlit_folium import st_folium

        m = folium.Map(location=[lat, lon], zoom_start=10)
        folium.Marker([lat, lon], popup="Vị trí trang trại").add_to(m)
        st_folium(m, width=700, height=400)


def render_preferences():
    st.subheader("🔧 Tùy chọn ứng dụng")

    user_data = db.get("users", {"email": st.user.email}) if hasattr(
        st, 'user') and st.user.is_logged_in else None
    user_data = user_data[0] if user_data else {}
    preferences = user_data.get('preferences', {})

    with st.form("preferences_form"):
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Cài đặt hiển thị**")
            theme = st.selectbox("Chủ đề", ["Sáng", "Tối", "Tự động"])
            dashboard_layout = st.selectbox(
                "Bố cục bảng điều khiển", ["Gọn", "Tiêu chuẩn", "Chi tiết"])
            auto_refresh = st.checkbox(
                "Tự động làm mới dữ liệu",
                value=preferences.get('auto_refresh', True))
            refresh_interval = st.slider(
                "Khoảng thời gian làm mới (giây)",
                30, 300, preferences.get('refresh_interval', 60))

        with col2:
            st.write("**Cài đặt thông báo**")
            email_notifications = st.checkbox(
                "Thông báo qua email",
                value=preferences.get('email_notifications', True))
            push_notifications = st.checkbox(
                "Thông báo đẩy",
                value=preferences.get('push_notifications', True))
            weather_alerts = st.checkbox(
                "Cảnh báo thời tiết",
                value=preferences.get('weather_alerts', True))
            irrigation_reminders = st.checkbox(
                "Nhắc nhở tưới tiêu",
                value=preferences.get('irrigation_reminders', True))

            st.write("---")
            one_signal_player_id = st.text_input(
                "ID người chơi OneSignal cho thông báo đẩy",
                value=user_data.get('one_signal_player_id', ''),
                help="Tìm ID này trong tài khoản OneSignal của bạn để nhận "
                "các cảnh báo quan trọng trên thiết bị của bạn.")

        st.write("**Dữ liệu & Quyền riêng tư**")
        data_sharing = st.checkbox(
            "Chia sẻ dữ liệu sử dụng ẩn danh để cải thiện",
            value=preferences.get('data_sharing', False))
        analytics = st.checkbox(
            "Bật theo dõi phân tích",
            value=preferences.get('analytics', True))

        if st.form_submit_button("💾 Lưu tùy chọn", type="primary"):
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
                'analytics': analytics}
            update_data = {
                'preferences': new_preferences,
                'one_signal_player_id': one_signal_player_id,
                'updated_at': datetime.now().isoformat()}

            if user_data:
                db.update("users", {"email": st.user.email}, update_data)
            else:
                user_data = {
                    **update_data,
                    'email': st.user.email,
                    'first_login': datetime.now().isoformat(),
                    'last_login': datetime.now().isoformat()}
                db.add("users", user_data)

            st.success("✅ Đã lưu tùy chọn!")
            st.rerun()

    st.subheader("🔌 Cấu hình API")

    with st.expander("Khóa API & Tích hợp"):
        st.write("**Trạng thái API hiện tại:**")

        api_key = st.secrets.get("gemini", {}).get("api_key", "")
        if api_key:
            st.success("✅ API Gemini: Đã định cấu hình")
        else:
            st.error("❌ API Gemini: Chưa được định cấu hình")

        st.info("🌤️ API Thời tiết: Open-Meteo (Miễn phí)")
        st.info("🛰️ API Vệ tinh: OpenET (NASA)")
        st.info("📡 API IoT: Máy chủ cục bộ")

        st.write(
            "**Lưu ý**: Các khóa API được định cấu hình trong tệp "
            "`.streamlit/secrets.toml`")


def render_security_settings():
    st.subheader("🔐 Bảo mật & Tài khoản")

    if hasattr(st, 'user') and st.user.is_logged_in:
        user_data = db.get("users", {"email": st.user.email})
        user_data = user_data[0] if user_data else {}

        st.write("**Thông tin tài khoản:**")
        col1, col2 = st.columns(2)

        with col1:
            st.metric("Email", st.user.email)
            st.metric(
                "Trạng thái tài khoản",
                "Hoạt động" if user_data.get('is_active', True)
                else "Không hoạt động")

        with col2:
            first_login = user_data.get('first_login', 'Không xác định')
            last_login = user_data.get('last_login', 'Không xác định')
            st.metric(
                "Thành viên từ",
                first_login[:10] if first_login != 'Không xác định'
                else 'Không xác định')
            st.metric(
                "Đăng nhập lần cuối",
                last_login[:10] if last_login != 'Không xác định'
                else 'Không xác định')

        st.subheader("📊 Quản lý dữ liệu")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("📤 Xuất dữ liệu của tôi", type="secondary"):
                export_data = {
                    "user_info": user_data,
                    "fields": db.get(
                        "fields", {"user_email": st.user.email}),
                    "iot_hubs": db.get(
                        "iot_hubs", {"user_email": st.user.email}),
                    "export_date": datetime.now().isoformat()}
                json_data = json.dumps(
                    export_data, indent=2, ensure_ascii=False)
                st.download_button(
                    label="Tải xuống JSON",
                    data=json_data,
                    file_name=f"terrasync_data_{st.user.email}_"
                    f"{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json")

        with col2:
            if st.button("🗑️ Xóa tài khoản", type="secondary"):
                st.warning("⚠️ Hành động này không thể hoàn tác!")
                if st.button("Xác nhận xóa", type="primary"):
                    db.delete("users", {"email": st.user.email})
                    db.delete("fields", {"user_email": st.user.email})
                    db.delete("iot_hubs", {"user_email": st.user.email})
                    st.success("✅ Xóa tài khoản thành công!")
                    st.info("Vui lòng làm mới trang để xem thay đổi")

        st.subheader("🔑 Quản lý phiên")

        if st.button("🚪 Đăng xuất tất cả các phiên", type="secondary"):
            st.info(
                "Tất cả các phiên sẽ được đăng xuất. "
                "Bạn sẽ cần đăng nhập lại.")

        st.subheader("🔒 Cài đặt quyền riêng tư")

        with st.form("privacy_form"):
            profile_visibility = st.selectbox(
                "Hiển thị hồ sơ", ["Công khai", "Riêng tư", "Chỉ bạn bè"])
            data_retention = st.selectbox(
                "Lưu giữ dữ liệu", [
                    "Giữ tất cả dữ liệu", "Tự động xóa sau 1 năm",
                    "Tự động xóa sau 2 năm"])
            marketing_emails = st.checkbox(
                "Nhận email tiếp thị",
                value=user_data.get('marketing_emails', False))

            if st.form_submit_button(
                    "💾 Lưu cài đặt quyền riêng tư", type="primary"):
                privacy_data = {
                    'profile_visibility': profile_visibility,
                    'data_retention': data_retention,
                    'marketing_emails': marketing_emails,
                    'updated_at': datetime.now().isoformat()}

                if user_data:
                    db.update(
                        "users", {"email": st.user.email}, privacy_data)
                else:
                    user_data = {
                        **privacy_data,
                        'email': st.user.email,
                        'first_login': datetime.now().isoformat(),
                        'last_login': datetime.now().isoformat()}
                    db.add("users", user_data)

                st.success("✅ Đã lưu cài đặt quyền riêng tư!")
                st.rerun()
    else:
        st.warning("Vui lòng đăng nhập để truy cập cài đặt bảo mật")

    st.subheader("ℹ️ Thông tin hệ thống")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Phiên bản ứng dụng:** 1.0.0")
        st.write("**Cơ sở dữ liệu:** SQLite/JSON")
        st.write("**Cập nhật lần cuối:** 2025-01-15")

    with col2:
        st.write("**Máy chủ:** Cục bộ")
        st.write("**Môi trường:** Phát triển")
        st.write("**Hỗ trợ:** support@terrasync.io")

