# utils/irrigation_logic.py
"""
Module for handling all irrigation-related calculations and logic.
"""
import logging
from database import db

logger = logging.getLogger(__name__)

# --- Constants ---
# Base reference evapotranspiration (ET0) in mm/day.
# This is a crucial assumption.
# Value for a sub-humid tropical region like Vietnam.
# Can be replaced by a weather API.
DEFAULT_ET0_MM_DAY = 4.5

# Average irrigation system flow rate in m³/hour per hectare.
# This is another assumption for calculating time.
DEFAULT_FLOW_RATE_M3_H_HA = 5.0


# --- Telemetry Helpers (Refactored from pages) ---

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
        # logger.warning(f"Không tìm thấy hub cho field {field_id}")
        return None

    telemetry_data = db.get("telemetry", {"hub_id": hub_id})
    if not telemetry_data:
        # logger.warning(f"Không tìm thấy telemetry cho hub {hub_id}")
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
        "rain_intensity": 0.0,
        "timestamp": latest_entry.get('timestamp')
    }

    nodes = data.get("soil_nodes", [])
    if nodes:
        values = [
            n['sensors']['soil_moisture'] for n in nodes if n.get(
                'sensors') and 'soil_moisture' in n['sensors']]
        if values:
            stats["avg_moisture"] = sum(values) / len(values)

    atm_node = data.get("atmospheric_node", {})
    if atm_node.get('sensors') and 'rain_intensity' in atm_node['sensors']:
        stats["rain_intensity"] = atm_node['sensors']['rain_intensity']

    return stats
