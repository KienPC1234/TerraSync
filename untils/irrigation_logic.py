# untils/irrigation_logic.py
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


# --- Core Calculation ---

def calculate_daily_water_needs(
        field: dict,
        et0_mm_day: float = DEFAULT_ET0_MM_DAY) -> dict:
    """
    Calculates the daily water requirement for a given field.

    Args:
        field (dict): The field document from the database.
        et0_mm_day (float): Reference evapotranspiration for the day (mm/day).

    Returns:
        dict: A dictionary with 'today_water' (m³) and 'time_needed' (hours).
    """
    area_ha = field.get('area', 0)
    kc = field.get('crop_coefficient', 1.0)
    irr_eff = field.get('irrigation_efficiency', 85)

    if area_ha <= 0:
        return {"today_water": 0, "time_needed": 0}

    # 1. Calculate Crop Evapotranspiration (ETc)
    # ETc (mm/day) = Kc * ET0
    etc_mm_day = kc * et0_mm_day

    # 2. Calculate water volume needed by the crop
    # Volume (Liters) = ETc (mm/day) * Area (m²)
    area_m2 = area_ha * 10000
    water_volume_liters = etc_mm_day * area_m2
    water_volume_m3 = water_volume_liters / 1000

    # 3. Adjust for irrigation system efficiency
    # Actual water to apply = Water needed / (Efficiency / 100)
    if irr_eff <= 0:
        irr_eff = 85  # fallback

    adjusted_water_m3 = water_volume_m3 / (irr_eff / 100.0)

    # 4. Calculate irrigation time
    # Time (hours) = Volume (m³) / Flow Rate (m³/hour)
    total_flow_rate_m3_hr = DEFAULT_FLOW_RATE_M3_H_HA * area_ha
    if total_flow_rate_m3_hr <= 0:
        time_needed_hours = 0
    else:
        time_needed_hours = adjusted_water_m3 / total_flow_rate_m3_hr

    return {
        "today_water": round(adjusted_water_m3, 2),
        "time_needed": round(time_needed_hours, 2)
    }


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
