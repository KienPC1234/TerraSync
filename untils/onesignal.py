import requests

ONESIGNAL_APP_ID = "YOUR_APP_ID"
ONESIGNAL_API_KEY = "YOUR_REST_API_KEY"

def send_push_notification(title, message, user_id=None):
    """Gửi thông báo qua OneSignal"""
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "included_segments": ["All"] if not user_id else None,
        "include_player_ids": [user_id] if user_id else None,
        "headings": {"en": title},
        "contents": {"en": message}
    }

    headers = {
        "Authorization": f"Basic {ONESIGNAL_API_KEY}",
        "Content-Type": "application/json"
    }

    r = requests.post("https://onesignal.com/api/v1/notifications",
                      json=payload, headers=headers)
    return r.json()
