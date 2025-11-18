import os
import requests  # Đã thêm thư viện requests
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Giả sử bạn có module này
from iot_api_client import get_iot_client 
from database import db, crop_db


def get_fields_from_db() -> Optional[List[Dict[str, Any]]]:
    """Lấy fields từ database cho user hiện tại"""
    try:
        import streamlit as st

        if hasattr(st, 'user') and st.user.is_logged_in:
            user_email = st.user.email
            if user_email:
                user_fields = db.get_fields_by_user(user_email)
                if user_fields:
                    return user_fields
    except Exception as e:
        print(f"Lỗi khi lấy dữ liệu từ database: {e}")
    return None


def get_api_base() -> str:
    base = os.getenv("IOT_API_BASE", "http://localhost:8000")
    return base.rstrip("/")


def fetch_latest_telemetry(hub_id: Optional[str] = None) -> Dict[str, Any]:
    client = get_iot_client()
    return client.get_latest_data(hub_id=hub_id) or {}


def fetch_history(
        hub_id: Optional[str] = None,
        limit: int = 50) -> List[Dict[str, Any]]:
    client = get_iot_client()
    return client.get_data_history(hub_id=hub_id, limit=limit)


def fetch_alerts(
        hub_id: Optional[str] = None,
        limit: int = 50) -> List[Dict[str, Any]]:
    client = get_iot_client()
    return client.get_alerts(hub_id=hub_id, limit=limit)


def _aggregate_soil_moisture(
        telemetry: Optional[Dict[str, Any]]) -> Optional[float]:
    if not telemetry:
        return None
    soil_nodes = telemetry.get("data", {}).get("soil_nodes", [])
    if not soil_nodes:
        return None
    
    values = []
    for node in soil_nodes:
        val = node.get("sensors", {}).get("soil_moisture")
        if val is not None:
            values.append(val)
            
    if not values:
        return None
        
    return sum(values) / len(values)


def get_latest_telemetry_stats(user_email: str, field_id: str) -> Dict[str, Any]:
    """
    Lấy thống kê telemetry mới nhất cho một field cụ thể.
    """
    hubs = db.get("iot_hubs", {"field_id": field_id, "user_email": user_email})
    if not hubs:
        return {}
    
    hub_id = hubs[0].get("hub_id")
    all_telemetry = db.get("telemetry", {"hub_id": hub_id})
    
    if not all_telemetry:
        return {}
        
    try:
        latest_entry = sorted(all_telemetry, key=lambda x: x.get('timestamp', ''), reverse=True)[0]
    except (IndexError, ValueError):
        return {}

    avg_moisture = _aggregate_soil_moisture(latest_entry)
    rain_intensity = 0.0
    timestamp = latest_entry.get("timestamp")
    
    data = latest_entry.get("data", {})
    if "atmospheric_node" in data:
        sensors = data["atmospheric_node"].get("sensors", {})
        rain_intensity = sensors.get("rain_intensity", 0.0)
        
    return {
        "avg_moisture": avg_moisture,
        "rain_intensity": rain_intensity,
        "timestamp": timestamp
    }


def fetch_forecast(lat: float, lon: float) -> Optional[List[Dict[str, Any]]]:
    """
    Hàm mới thêm: Lấy dự báo thời tiết từ Open-Meteo API.
    """
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,precipitation,wind_speed_10m",
            "timezone": "auto"
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        hourly = data.get("hourly", {})
        
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        precips = hourly.get("precipitation", [])
        winds = hourly.get("wind_speed_10m", [])
        
        formatted_data = []
        # Chỉ lấy tối đa khoảng 168 giờ (7 ngày) hoặc ít hơn tùy dữ liệu trả về
        count = min(len(times), len(temps), len(precips), len(winds))
        
        for i in range(count):
            formatted_data.append({
                "time": times[i],
                "temperature": temps[i],
                "precipitation": precips[i],
                "wind_speed": winds[i]
            })
            
        return formatted_data

    except Exception as e:
        print(f"Lỗi khi lấy dữ liệu thời tiết: {e}")
        return None


def generate_schedule(
        telemetry: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    schedule: List[Dict[str, Any]] = []
    base_date = datetime.now()
    baseline = 450.0
    moisture = _aggregate_soil_moisture(telemetry)
    adjustment = 0.0
    if moisture is not None:
        adjustment = max(-200.0, min(200.0, (50.0 - moisture) * 6.0))
    for i in range(7):
        date = base_date + timedelta(days=i)
        water = max(150.0, baseline + i * 10.0 + adjustment)
        schedule.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "water": round(water, 1),
                "end_time": "13:00",
            }
        )
    return schedule


def predict_water_needs(
        field: Dict[str, Any],
        telemetry: Optional[Dict[str, Any]]) -> float:
    """
    Dự đoán lượng nước cần thiết (m3).
    """
    crop_type = field.get("crop")
    all_crops = crop_db.get("crops")
    crop_info = next((c for c in all_crops if c.get("name") == crop_type), None)

    if not crop_info:
        return 0.0

    current_stage_name = field.get("stage", "development").lower()
    water_needs_by_stage = crop_info.get("water_needs", {})
    Kc = water_needs_by_stage.get(current_stage_name, crop_info.get("crop_coefficient", 1.0))

    soil_moisture = None
    if telemetry:
        soil_moisture = _aggregate_soil_moisture(telemetry)

    rain_intensity = 0.0
    if telemetry and "atmospheric_node" in telemetry.get("data", {}):
        sensors = telemetry["data"]["atmospheric_node"].get("sensors", {})
        rain_intensity = sensors.get("rain_intensity", 0.0)

    ETo = 5.0
    ETc = ETo * Kc

    if soil_moisture is not None:
        mad_threshold = 50.0
        if soil_moisture < mad_threshold:
            moisture_deficit = mad_threshold - soil_moisture
            water_from_moisture = (moisture_deficit / 100.0) * ETc * 2
        else:
            water_from_moisture = 0.0
        water_needed_mm = ETc + water_from_moisture
    else:
        water_needed_mm = ETc

    effective_rain = rain_intensity * 0.8
    water_needed_mm = max(0.0, water_needed_mm - effective_rain)

    area_sqm = field.get("area", 0) * 4046.86 
    total_liters = water_needed_mm * area_sqm

    return round(total_liters / 1000.0, 2)


def check_warnings(
        field: Dict[str, Any],
        telemetry: Optional[Dict[str, Any]]) -> List[str]:
    """
    Kiểm tra các điều kiện cảnh báo.
    """
    warnings = []
    crop_type = field.get("crop")
    all_crops = crop_db.get("crops")
    crop_info = next((c for c in all_crops if c.get("name") == crop_type), None)

    if not crop_info or not telemetry:
        return warnings

    crop_warnings = crop_info.get("warnings", {})
    temp_warning = crop_warnings.get("nhiet_do")
    humid_warning = crop_warnings.get("do_am")

    air_temperature = None
    air_humidity = None

    if "atmospheric_node" in telemetry.get("data", {}):
        sensors = telemetry["data"]["atmospheric_node"].get("sensors", {})
        air_temperature = sensors.get("air_temperature")
        air_humidity = sensors.get("air_humidity")

    if temp_warning and air_temperature is not None:
        if air_temperature < temp_warning.get("min"):
            warnings.append(
                f"Nhiệt độ không khí thấp: {air_temperature}°C. "
                f"Ngưỡng: {temp_warning.get('min')}°C")
        if air_temperature > temp_warning.get("max"):
            warnings.append(
                f"Nhiệt độ không khí cao: {air_temperature}°C. "
                f"Ngưỡng: {temp_warning.get('max')}°C")

    if humid_warning and air_humidity is not None:
        if air_humidity < humid_warning.get("min"):
            warnings.append(
                f"Độ ẩm không khí thấp: {air_humidity}%. "
                f"Ngưỡng: {humid_warning.get('min')}%")
        if air_humidity > humid_warning.get("max"):
            warnings.append(
                f"Độ ẩm không khí cao: {air_humidity}%. "
                f"Ngưỡng: {humid_warning.get('max')}%")

    return warnings