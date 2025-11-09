import json
import time
import sys
import os
from datetime import datetime, timezone

# Add parent directory to path to import database and onesignal
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import db

# --- ĐÃ THAY ĐỔI: Import send_email thay vì send_push_notification ---
try:
    from utils.email_sender import send_email
except ImportError:
    print("Cảnh báo: Không thể import 'utils.email_sender'. Chức năng email sẽ không hoạt động.")
    # Tạo hàm giả để code không bị lỗi
    def send_email(*args, **kwargs):
        print("Lỗi: send_email chưa được cấu hình (không tìm thấy utils/email_sender.py).")
        return None
# --- KẾT THÚC THAY ĐỔI ---


# Constants
CHECK_INTERVAL_SECONDS = 30  # 5 minutes
DB_FILE_PATH = os.path.abspath('terrasync_db.json')
print ("DB:",str(DB_FILE_PATH))
# --- Các hằng số cho logic tưới tiêu ---
LOW_MOISTURE_THRESHOLD = 30.0    # Ngưỡng độ ẩm thấp (cần tưới)
HIGH_MOISTURE_THRESHOLD = 80.0   # Ngưỡng độ ẩm cao (ngừng tưới)
RAIN_INTENSITY_THRESHOLD = 1.0   # Ngưỡng mưa (mm/h) để coi là "đang mưa"

# =====================================================================
# --- HÀM XỬ LÝ ALERTS (ĐÃ SỬA) ---
# =====================================================================

def get_user_by_email(email: str):
    """Fetches a user from the database by their email."""
    users = db.get_all('users')
    for user in users:
        if user.get('email') == email:
            return user
    return None

def get_hub_owner_email(hub_id: str):
    """Fetches the owner's email for a given hub_id."""
    hubs = db.get_all('iot_hubs')
    for hub in hubs:
        if hub.get('hub_id') == hub_id:
            return hub.get('user_email')
    return None

def process_alerts():
    """
    Xử lý các cảnh báo khẩn cấp, gửi EMAIL,
    và đánh dấu là đã gửi.
    """
    print(f"[{datetime.now()}] Checking for new critical alerts...")
    
    try:
        alerts = db.get_all('alerts')
        if not alerts:
            print("No alerts found.")
            return

        notifications_sent = 0
        all_alerts_copy = list(alerts) # Làm việc trên bản copy

        for i, alert in enumerate(all_alerts_copy):
            # Chỉ xử lý cảnh báo 'critical' chưa được gửi
            if alert.get('level') == 'critical' and not alert.get('notification_sent'):
                hub_id = alert.get('hub_id')
                user_email = get_hub_owner_email(hub_id)
                
                if not user_email:
                    print(f"Warning: Could not find owner for hub_id {hub_id}. Skipping alert.")
                    continue

                # Kiểm tra user tồn tại (vẫn hữu ích)
                user = get_user_by_email(user_email)
                if not user:
                    print(f"Warning: Could not find user with email {user_email}. Skipping alert.")
                    continue
                
                # Không cần player_id nữa
                
                title = "🚨 Cảnh báo Nông trại Khẩn cấp!"
                message = alert.get('message', "Một sự kiện khẩn cấp đã xảy ra tại vườn của bạn.")
                
                print(f"Sending EMAIL to {user_email} for hub {hub_id}...")
                
                # --- ĐÃ THAY ĐỔI: Gọi send_email ---
                result = send_email(
                    subject=title,
                    body=message,
                    to_email=user_email 
                )
                # --- KẾT THÚC THAY ĐỔI ---

                # Logic kiểm tra kết quả (dựa trên 'status' thay vì 'id')
                if result and result.get('status') == 'success':
                    print(f"Successfully sent email notification (ID: {result.get('id', 'sent')})")
                    # Đánh dấu là đã gửi
                    alert['notification_sent'] = True
                    alert['notification_sent_at'] = datetime.now(timezone.utc).isoformat()
                    notifications_sent += 1
                    
                    # Cập nhật lại vào DB (dùng index)
                    db.update('alerts', i, alert)
                else:
                    print(f"Error sending email: {result.get('message') if result else 'Unknown error'}")

        if notifications_sent > 0:
            print(f"Finished processing. Sent {notifications_sent} new critical emails.")
        else:
            print("No new critical alerts to notify.")

    except Exception as e:
        print(f"An unexpected error occurred during process_alerts: {e}")


# =====================================================================
# --- HÀM TÍNH TOÁN TƯỚI TIÊU (Giữ nguyên) ---
# =====================================================================

def get_field_by_id(fields_list, field_id):
    """Helper: Tìm field và index của nó trong danh sách."""
    for i, field in enumerate(fields_list):
        if field.get('id') == field_id:
            return field, i
    return None, -1

def get_latest_telemetry_for_hub(telemetry_list, hub_id):
    """Helper: Lấy bản tin telemetry mới nhất cho hub."""
    hub_telemetry = [t for t in telemetry_list if t.get('hub_id') == hub_id]
    if not hub_telemetry:
        return None
    # Sắp xếp theo timestamp, mới nhất lên đầu
    hub_telemetry.sort(key=lambda x: x.get('timestamp', '1970-01-01T00:00:00+00:00'), reverse=True)
    return hub_telemetry[0]

def average_soil_moisture(telemetry_data):
    """Helper: Tính độ ẩm đất trung bình từ gói telemetry."""
    if not telemetry_data or 'data' not in telemetry_data:
        return None
    nodes = telemetry_data['data'].get('soil_nodes', [])
    if not nodes:
        return None
    values = [n['sensors']['soil_moisture'] for n in nodes if n.get('sensors') and 'soil_moisture' in n['sensors']]
    if not values:
        return None
    return sum(values) / len(values)

def calculate_auto_irrigation():
    """
    Tự động tính toán và cập nhật trạng thái tưới tiêu cho các vườn (fields)
    dựa trên dữ liệu telemetry mới nhất.
    """
    print(f"[{datetime.now()}] Running automatic irrigation calculations...")
    
    try:
        # 1. Tải tất cả các bảng cần thiết từ DB
        all_hubs = db.get_all('iot_hubs')
        all_fields = db.get_all('fields') # Dùng bảng 'fields' gốc
        all_telemetry = db.get_all('telemetry')

        if not all_hubs or not all_fields:
            print("No hubs or fields found. Skipping irrigation logic.")
            return

        fields_updated = 0

        # 2. Lặp qua từng Hub
        for hub in all_hubs:
            hub_id = hub.get('hub_id')
            field_id = hub.get('field_id')
            if not hub_id or not field_id:
                continue

            # 3. Tìm Field (vườn) tương ứng và index của nó
            field, field_index = get_field_by_id(all_fields, field_id)
            if not field:
                print(f"Warning: Hub {hub_id} is linked to a non-existent field {field_id}.")
                continue

            # 4. Tìm Telemetry mới nhất cho Hub này
            latest_telemetry = get_latest_telemetry_for_hub(all_telemetry, hub_id)
            if not latest_telemetry:
                print(f"No telemetry found for hub {hub_id}. Skipping field '{field.get('name')}'.")
                continue

            # 5. Lấy các chỉ số cảm biến
            avg_moisture = average_soil_moisture(latest_telemetry)
            rain_intensity = latest_telemetry.get('data', {}).get('atmospheric_node', {}).get('sensors', {}).get('rain_intensity', 0)

            # 6. Áp dụng Logic Tưới tiêu
            field_changed = False
            new_status = field.get('status')
            new_progress = field.get('progress')
            new_time_needed = field.get('time_needed')

            # Logic 1: Nếu trời đang mưa, đánh dấu là đã tưới
            if rain_intensity > RAIN_INTENSITY_THRESHOLD:
                if new_status != 'hydrated' or new_progress != 100:
                    new_status = 'hydrated'
                    new_progress = 100
                    new_time_needed = 0
                    field_changed = True
                    print(f"Field '{field.get('name')}': Đang mưa. Dừng tưới.")
            
            # Logic 2: Nếu đất quá khô (và không mưa)
            elif avg_moisture is not None and avg_moisture < LOW_MOISTURE_THRESHOLD:
                if new_status != 'dehydrated':
                    new_status = 'dehydrated'
                    new_progress = 0
                    new_time_needed = 2 # Ví dụ: cần 2 giờ tưới
                    field_changed = True
                    print(f"Field '{field.get('name')}': Đất khô ({avg_moisture}%). Cần tưới.")
            
            # Logic 3: Nếu đất quá ẩm (và không mưa)
            elif avg_moisture is not None and avg_moisture > HIGH_MOISTURE_THRESHOLD:
                 if new_status != 'hydrated' or new_progress != 100:
                    new_status = 'hydrated'
                    new_progress = 100
                    new_time_needed = 0
                    field_changed = True
                    print(f"Field '{field.get('name')}': Đất ẩm ({avg_moisture}%). Ngừng tưới.")

            # Logic 4: Nếu đất ở mức tốt (và không mưa)
            elif avg_moisture is not None:
                # Nếu trước đó đang 'cần tưới' (dehydrated)
                if new_status == 'dehydrated':
                    new_status = 'hydrated' # Chuyển sang 'hydrated'
                    new_progress = 100     # Đánh dấu hoàn thành
                    new_time_needed = 0
                    field_changed = True
                    print(f"Field '{field.get('name')}': Độ ẩm tốt ({avg_moisture}%).")

            # 7. Cập nhật thay đổi vào DB (nếu có)
            if field_changed:
                field['status'] = new_status
                field['progress'] = new_progress
                field['time_needed'] = new_time_needed
                
                # Cập nhật bằng index, giống như cách process_alerts làm
                db.update('fields', field_index, field)
                fields_updated += 1
        
        if fields_updated > 0:
            print(f"Finished irrigation calculations. Updated {fields_updated} fields.")
        else:
            print("Irrigation calculations complete. No fields required updates.")

    except Exception as e:
        print(f"An unexpected error occurred during calculate_auto_irrigation: {e}")


# =====================================================================
# --- HÀM CHÍNH (MAIN LOOP) ---
# =====================================================================

def main():
    """Main loop for the background job."""
    print("Starting TerraSync Background Job...")
    while True:
        # 1. Xử lý alerts và gửi thông báo
        process_alerts()
        
        # 2. Chạy logic tưới tiêu tự động
        calculate_auto_irrigation()
        
        print(f"--- Cycle complete. Sleeping for {CHECK_INTERVAL_SECONDS} seconds ---")
        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()