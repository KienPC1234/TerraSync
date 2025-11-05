
import json
import time
import sys
import os
from datetime import datetime, timezone

# Add parent directory to path to import database and onesignal
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import db
from untils.onesignal import send_push_notification

# Constants
CHECK_INTERVAL_SECONDS = 300  # 5 minutes
DB_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'terrasync_db.json')

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
    Processes critical alerts that have not been sent yet,
    sends notifications, and marks them as sent.
    """
    print(f"[{datetime.now()}] Checking for new critical alerts...")
    
    try:
        alerts = db.get_all('alerts')
        if not alerts:
            print("No alerts found.")
            return

        updated_alerts = []
        notifications_sent = 0
        
        # We need to iterate over a copy, as we might modify it
        all_alerts_copy = list(alerts)

        for i, alert in enumerate(all_alerts_copy):
            # Process only critical alerts that haven't been notified yet
            if alert.get('level') == 'critical' and not alert.get('notification_sent'):
                hub_id = alert.get('hub_id')
                user_email = get_hub_owner_email(hub_id)
                
                if not user_email:
                    print(f"Warning: Could not find owner for hub_id {hub_id}. Skipping alert.")
                    continue

                user = get_user_by_email(user_email)
                if not user:
                    print(f"Warning: Could not find user with email {user_email}. Skipping alert.")
                    continue
                
                player_id = user.get('one_signal_player_id')
                
                if player_id:
                    title = "🚨 Critical Farm Alert!"
                    message = alert.get('message', "A critical event has occurred on your farm.")
                    
                    print(f"Sending notification to {user_email} for hub {hub_id}...")
                    
                    # Send notification
                    result = send_push_notification(
                        title=title,
                        message=message,
                        external_ids=[user_email] # Using external_id is more robust
                    )

                    if result and result.get('id'):
                        print(f"Successfully sent notification {result.get('id')}")
                        # Mark as sent
                        alert['notification_sent'] = True
                        alert['notification_sent_at'] = datetime.now(timezone.utc).isoformat()
                        notifications_sent += 1
                    else:
                        print(f"Error sending notification: {result.get('errors')}")
                else:
                    print(f"User {user_email} has not configured their OneSignal Player ID. Skipping notification.")
                
                # Update the original list
                db.update('alerts', i, alert)


        if notifications_sent > 0:
            print(f"Finished processing. Sent {notifications_sent} new critical notifications.")
        else:
            print("No new critical alerts to notify.")

    except FileNotFoundError:
        print(f"Error: Database file not found at {DB_FILE_PATH}")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {DB_FILE_PATH}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def main():
    """Main loop for the background job."""
    print("Starting TerraSync Background Job...")
    while True:
        process_alerts()
        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
