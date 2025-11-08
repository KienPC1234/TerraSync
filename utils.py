import math
import os
import random
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from iot_api_client import get_iot_client


DEFAULT_FIELDS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "Blueberry Field",
        "crop": "Blueberry",
        "area": 675.45,
        "status": "hydrated",
        "today_water": 80,
        "time_needed": 4,
        "progress": 95,
        "days_to_harvest": 48,
        "lat": 35.6229,
        "lon": -120.6933,
        "stage": "Adult",
        "node_id": "soil-01",
        "center": [35.6229, -120.6933],
        "polygon": [
            [35.6225, -120.6938],
            [35.6230, -120.6938],
            [35.6230, -120.6928],
            [35.6225, -120.6928],
        ],
    },
    {
        "id": 2,
        "name": "Avocado Field",
        "crop": "Avocado",
        "area": 585.39,
        "status": "dehydrated",
        "today_water": 63,
        "time_needed": 3.5,
        "progress": 32,
        "days_to_harvest": 120,
        "lat": 35.6235,
        "lon": -120.6940,
        "stage": "Adult",
        "node_id": "soil-02",
        "center": [35.6235, -120.6940],
        "polygon": [
            [35.6230, -120.6945],
            [35.6240, -120.6945],
            [35.6240, -120.6935],
            [35.6230, -120.6935],
        ],
    },
    {
        "id": 3,
        "name": "Corn Field A",
        "crop": "Corn",
        "area": 720.48,
        "status": "severely_dehydrated",
        "today_water": 157,
        "time_needed": 11,
        "progress": 0,
        "days_to_harvest": 90,
        "lat": 35.6215,
        "lon": -120.6920,
        "stage": "Seedling",
        "node_id": "soil-03",
        "center": [35.6215, -120.6920],
        "polygon": [
            [35.6210, -120.6925],
            [35.6220, -120.6925],
            [35.6220, -120.6915],
            [35.6210, -120.6915],
        ],
    },
]

CROP_DB = {
    "Blueberry": {
        "water_requirements": 80,
        "growth_stages": ["Seedling", "Juvenile", "Adult", "Fruiting"]
    },
    "Avocado": {
        "water_requirements": 120,
        "growth_stages": ["Seedling", "Juvenile", "Adult", "Fruiting"]
    },
    "Corn": {
        "water_requirements": 150,
        "growth_stages": ["Seedling", "Vegetative", "Reproductive", "Maturity"]
    }
}

def add_crop(name: str, characteristics: Dict[str, Any]):
    """Add new crop to database"""
    CROP_DB[name] = characteristics
    # In a real implementation, save to database

def generate_crop_characteristics(name: str) -> Dict[str, Any]:
    """AI-generated placeholder for crop characteristics"""
    return {
        "water_requirements": random.randint(50, 200),
        "growth_stages": ["Seedling", "Growth", "Maturity"]
    }

def get_default_fields() -> List[Dict[str, Any]]:
    return deepcopy(DEFAULT_FIELDS)

def get_fields_from_db() -> Optional[List[Dict[str, Any]]]:
    """Lấy fields từ database cho user hiện tại"""
    try:
        from database import db
        import streamlit as st
        
        if hasattr(st, 'user') and st.user.is_logged_in:
            user_email = st.user.email
            if user_email:
                user_fields = db.get_user_fields(user_email)
                if user_fields:
                    return user_fields
    except Exception as e:
        print(f"Error getting fields from database: {e}")
    return None


def get_api_base() -> str:
    base = os.getenv("IOT_API_BASE", "http://localhost:8000")
    return base.rstrip("/")


def fetch_latest_telemetry(hub_id: Optional[str] = None) -> Dict[str, Any]:
    client = get_iot_client()
    return client.get_latest_data(hub_id=hub_id) or {}


def fetch_history(hub_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    client = get_iot_client()
    return client.get_data_history(hub_id=hub_id, limit=limit)


def fetch_alerts(hub_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    client = get_iot_client()
    return client.get_alerts(hub_id=hub_id, limit=limit)


def _aggregate_soil_moisture(telemetry: Optional[Dict[str, Any]]) -> Optional[float]:
    if not telemetry:
        return None
    soil_nodes = telemetry.get("data", {}).get("soil_nodes", [])
    if not soil_nodes:
        return None
    total = sum(node.get("sensors", {}).get("soil_moisture", 0.0) for node in soil_nodes)
    return total / len(soil_nodes)


def generate_schedule(telemetry: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
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


def _jitter(value: float, spread: float) -> float:
    return value + random.uniform(-spread, spread)


def generate_demo_payload(
    hub_id: Optional[str] = None,
    base_payload: Optional[Dict[str, Any]] = None,
    include_third_node: bool = True,
) -> Dict[str, Any]:
    payload = deepcopy(base_payload or {})
    payload["hub_id"] = hub_id or os.getenv("DEMO_HUB_ID", "demo-hub-001")
    now = datetime.now(timezone.utc)
    payload["timestamp"] = now.isoformat().replace("+00:00", "Z")
    if payload.get("location"):
        payload["location"]["lat"] = round(_jitter(payload["location"]["lat"], 0.0012), 6)
        payload["location"]["lon"] = round(_jitter(payload["location"]["lon"], 0.0012), 6)

    soil_nodes = payload.setdefault("data", {}).setdefault("soil_nodes", [])
    if include_third_node and not any(node.get("node_id") == "soil-03" for node in soil_nodes):
        soil_nodes.append(
            {
                "node_id": "soil-03",
                "sensors": {"soil_moisture": 28.4, "soil_temperature": 25.4},
            }
        )

    for node in soil_nodes:
        sensors = node.setdefault("sensors", {})
        base_moisture = sensors.get("soil_moisture", 35.0)
        sensors["soil_moisture"] = round(max(5.0, min(95.0, base_moisture + random.uniform(-6.0, 6.0))), 1)
        base_temp = sensors.get("soil_temperature", 26.0)
        sensors["soil_temperature"] = round(base_temp + random.uniform(-1.6, 1.6), 1)

    atm_sensors = (
        payload.setdefault("data", {})
        .setdefault("atmospheric_node", {})
        .setdefault("sensors", {})
    )
    atm_sensors["air_temperature"] = round(atm_sensors.get("air_temperature", 30.0) + random.uniform(-1.8, 1.8), 1)
    atm_sensors["air_humidity"] = round(max(30.0, min(99.0, atm_sensors.get("air_humidity", 70.0) + random.uniform(-4.5, 4.5))), 1)
    atm_sensors["rain_intensity"] = round(max(0.0, atm_sensors.get("rain_intensity", 0.0) + random.uniform(-0.5, 2.5)), 2)
    atm_sensors["wind_speed"] = round(max(0.0, atm_sensors.get("wind_speed", 2.0) + random.uniform(-0.8, 1.2)), 2)
    atm_sensors["light_intensity"] = round(max(100.0, atm_sensors.get("light_intensity", 900.0) + random.uniform(-120.0, 150.0)), 1)
    atm_sensors["barometric_pressure"] = round(atm_sensors.get("barometric_pressure", 1008.0) + random.uniform(-2.2, 2.2), 1)

    payload.setdefault("meta", {})["ingest_id"] = str(uuid4())
    return payload


def send_demo_payload(
    api_base: Optional[str] = None,
    hub_id: Optional[str] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    payload = generate_demo_payload(hub_id=hub_id)
    base = api_base or get_api_base()
    try:
        response = requests.post(
            f"{base}/api/v1/data/ingest",
            json=payload,
            timeout=8,
        )
        if response.status_code == 200:
            meta = response.json()
            return True, "Demo telemetry injected", {"payload": payload, "response": meta}
        return (
            False,
            f"IoT API responded with status {response.status_code}: {response.text}",
            {"payload": payload},
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"Failed to reach IoT API: {exc}", {"payload": payload}


def fetch_forecast(
    lat: float,
    lon: float,
    hours: int = 24,
    api_endpoint: str = "https://api.open-meteo.com/v1/forecast",
) -> List[Dict[str, Any]]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation,wind_speed_10m,weathercode",
        "forecast_days": 1,
        "timezone": "UTC",
    }
    try:
        response = requests.get(api_endpoint, params=params, timeout=6)
        if response.status_code == 200:
            payload = response.json()
            hourly = payload.get("hourly", {})
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            prec = hourly.get("precipitation", [])
            wind = hourly.get("wind_speed_10m", [])
            code = hourly.get("weathercode", [])
            forecast: List[Dict[str, Any]] = []
            for idx, t in enumerate(times[:hours]):
                forecast.append(
                    {
                        "time": t,
                        "temperature": temps[idx] if idx < len(temps) else None,
                        "precipitation": prec[idx] if idx < len(prec) else None,
                        "wind_speed": wind[idx] if idx < len(wind) else None,
                        "weather_code": code[idx] if idx < len(code) else None,
                    }
                )
            if forecast:
                return forecast
    except Exception:
        return [] # Return empty list instead of sample forecast
    return [] # Return empty list instead of sample forecast

def predict_water_needs(field: Dict[str, Any], telemetry: Optional[Dict[str, Any]]) -> float:
    """
    Dự đoán lượng nước cần thiết cho một ruộng dựa trên dữ liệu IoT.
    """
    water_needed = 0.0

    # Lấy thông tin cây trồng
    crop_type = field.get("crop")
    crop_info = CROP_DB.get(crop_type, {})
    base_water_requirement = crop_info.get("water_requirements", 100) # Mặc định 100mm

    # Lấy dữ liệu độ ẩm đất từ telemetry
    soil_moisture = None
    if telemetry and "soil_nodes" in telemetry.get("data", {}):
        for node in telemetry["data"]["soil_nodes"]:
            if node.get("node_id") == field.get("node_id"):
                soil_moisture = node.get("sensors", {}).get("soil_moisture")
                break
    
    # Lấy dữ liệu lượng mưa từ telemetry
    rain_intensity = 0.0
    if telemetry and "atmospheric_node" in telemetry.get("data", {}):
        rain_intensity = telemetry["data"]["atmospheric_node"].get("sensors", {}).get("rain_intensity", 0.0)

    if soil_moisture is not None:
        # Giả định độ ẩm lý tưởng là 60%
        ideal_moisture = 60.0
        moisture_deficit = max(0.0, ideal_moisture - soil_moisture)
        
        # Tính toán lượng nước cần dựa trên thiếu hụt độ ẩm và yêu cầu cơ bản của cây
        # Hệ số điều chỉnh dựa trên diện tích (ví dụ: 1 acre = 4046.86 m^2)
        area_sqm = field.get("area", 1.0) * 4046.86
        # Chuyển đổi từ % độ ẩm sang mm nước (giả định 1% độ ẩm = X mm nước)
        # Đây là một ước tính rất thô, cần mô hình phức tạp hơn cho thực tế
        water_from_moisture = (moisture_deficit / 100.0) * base_water_requirement * (area_sqm / 1000.0) # Đơn vị lít
        
        water_needed = water_from_moisture

    # Giảm lượng nước cần nếu có mưa
    # Giả định 1mm mưa trên 1m^2 = 1 lít nước
    water_from_rain = rain_intensity * field.get("area", 1.0) * 4046.86 / 1000.0 # Đơn vị lít
    water_needed = max(0.0, water_needed - water_from_rain)

    # Chuyển đổi sang lít/ngày (ước tính)
    return round(water_needed, 2)