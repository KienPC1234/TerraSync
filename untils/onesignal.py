import requests

# TODO: Replace with your OneSignal App ID and REST API Key
ONESIGNAL_APP_ID = "YOUR_ONESIGNAL_APP_ID"
ONESIGNAL_API_KEY = "YOUR_ONESIGNAL_REST_API_KEY"

def send_push_notification(title, message, user_id=None, external_ids: list = None):
    """
    Gửi thông báo đẩy (push notification) qua OneSignal.

    Args:
        title (str): Tiêu đề của thông báo.
        message (str): Nội dung của thông báo.
        user_id (str, optional): OneSignal player ID của người dùng cụ thể. Defaults to None.
        external_ids (list, optional): Danh sách external_id (ví dụ: email) của người dùng. Defaults to None.
    """
    if not ONESIGNAL_APP_ID or "YOUR_ONESIGNAL" in ONESIGNAL_APP_ID:
        print("📢 OneSignal is not configured. Skipping push notification.")
        return {"status": "skipped", "message": "OneSignal not configured"}

    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "headings": {"en": title},
        "contents": {"en": message}
    }

    if external_ids:
        payload["include_external_user_ids"] = external_ids
    elif user_id:
        payload["include_player_ids"] = [user_id]
    else:
        payload["included_segments"] = ["All"]

    headers = {
        "Authorization": f"Basic {ONESIGNAL_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        r = requests.post("https://onesignal.com/api/v1/notifications",
                          json=payload, headers=headers)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending OneSignal notification: {e}")
        return {"status": "error", "message": str(e)}

