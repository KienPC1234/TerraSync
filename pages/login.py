import streamlit as st

def render_login():
    """
    Trang đăng nhập OAuth Google cho TerraSync.
    """
    st.title("🌱 TerraSync IoT: Hệ Thống Nông Nghiệp Thông Minh")

    st.markdown("""
    **Tích Hợp IoT Và AI Cho Quản Lý Nước & Ruộng Bền Vững**  
    TerraSync kết nối cảm biến thực địa, AI dự báo thời tiết và vệ tinh để giúp nông dân tối ưu tưới tiêu, phát hiện bệnh sớm và tăng năng suất.
    ---
    """)

    if not st.user.is_logged_in:
        st.subheader("🔐 Đăng nhập để bắt đầu")
        st.markdown("Sử dụng tài khoản Google để truy cập hệ thống TerraSync.")
        
        # Gọi hàm login mới
        if st.button("🔑 Đăng nhập bằng Google", type="primary", use_container_width=True):
            st.login()
        
        st.info("Hãy đảm bảo bạn đăng nhập bằng tài khoản Google hợp lệ.")
    else:
        st.success(f"Chào mừng trở lại, **{st.user.name or st.user.email}** 🌾")
        if st.button("🚪 Đăng xuất", type="secondary"):
            logout()

def logout():
    """Đăng xuất bằng API Streamlit mới."""
    st.logout()
