import smtplib
import ssl
from email.message import EmailMessage
import streamlit as st

# Lấy thông tin cấu hình từ Streamlit Secrets (an toàn hơn)
smtp_config = st.secrets.get("smtp", {})
SMTP_SERVER = smtp_config.get("server", "")
SMTP_PORT = smtp_config.get("port", 587)
SENDER_EMAIL = smtp_config.get("email", "")
SENDER_PASSWORD = smtp_config.get("password")  # Sẽ là None nếu không có


def send_email(subject: str, body: str, to_email: str):
    """
    Gửi email thông báo sử dụng SMTP.

    Args:
        subject (str): Tiêu đề của email.
        body (str): Nội dung (text) của email.
        to_email (str): Email của người nhận.
    """

    # Kiểm tra cấu hình
    if not SENDER_PASSWORD:
        print("################################################################")
        print("### 📢 WARNING: SMTP is not configured.                      ###")
        print("### Please set [smtp] section in .streamlit/secrets.toml   ###")
        print("################################################################")
        return {
            "status": "skipped",
            "message": "SMTP not configured in Streamlit Secrets"}

    # Tạo đối tượng EmailMessage
    msg = EmailMessage()
    msg['Subject'] = f"[TerraSync] {subject}"
    msg['From'] = f"TerraSync Alerts <{SENDER_EMAIL}>"
    msg['To'] = to_email
    msg.set_content(body)  # Nội dung text đơn giản

    # Thêm phiên bản HTML (để email đẹp hơn)
    msg.add_alternative(f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
            .container {{
                width: 90%;
                margin: auto;
                padding: 20px;
                border: 1px solid #ddd;
                border-radius: 5px;
            }}
            .header {{
                font-size: 24px;
                color: #d9534f;
                font-weight: bold;
            }}
            .content {{ margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">{subject}</div>
            <div class="content">
                <p>Xin chào,</p>
                <p>{body.replace('\\n', '<br>')}</p>
                <br>
                <p>Trân trọng,<br>Đội ngũ TerraSync</p>
            </div>
        </div>
    </body>
    </html>
    """, subtype='html')

    try:
        # Tạo context SSL an toàn
        context = ssl.create_default_context()

        print(
            f"Connecting to SMTP server {SMTP_SERVER} on port {SMTP_PORT}...")

        # Sử dụng smtplib.SMTP cho cổng 587 (STARTTLS)
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=context)  # Nâng cấp lên kết nối an toàn
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        print(f"Successfully sent email to {to_email}")
        # Lấy Message-ID làm ID trả về nếu có
        return {"status": "success", "id": msg.get('Message-ID', "sent")}

    except smtplib.SMTPException as e:
        print(f"Error sending email: {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {"status": "error", "message": str(e)}
