# utils.py - Utilities Remain
import math
import os
import random
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import requests

SAMPLE_TELEMETRY: Dict[str, Any] = {
    "hub_id": "c72b56e1-1b9a-46a8-a7b8-0a6ef27b3b72",
    "timestamp": "2025-10-22T13:42:00Z",
    "location": {"lat": 20.4512, "lon": 106.3312},
    "data": {
        "soil_nodes": [
            {
                "node_id": "soil-01",
                "sensors": {"soil_moisture": 31.4, "soil_temperature": 27.8},
            },
            {
                "node_id": "soil-02",
                "sensors": {"soil_moisture": 40.1, "soil_temperature": 26.2},
            },
            {
                "node_id": "soil-03",
                "sensors": {"soil_moisture": 22.7, "soil_temperature": 25.4},
            },
        ],
        "atmospheric_node": {
            "node_id": "atm-01",
            "sensors": {
                "air_temperature": 30.7,
                "air_humidity": 70.2,
                "rain_intensity": 0.0,
                "wind_speed": 1.8,
                "light_intensity": 950.0,
                "barometric_pressure": 1007.6,
            },
        },
    },
}

SAMPLE_HISTORY: List[Dict[str, Any]] = [
    {
        "hub_id": SAMPLE_TELEMETRY["hub_id"],
        "timestamp": "2025-10-22T12:42:00Z",
        "data": {
            "soil_nodes": [
                {
                    "node_id": "soil-01",
                    "sensors": {"soil_moisture": 34.5, "soil_temperature": 27.4},
                },
                {
                    "node_id": "soil-02",
                    "sensors": {"soil_moisture": 42.3, "soil_temperature": 26.0},
                },
                {
                    "node_id": "soil-03",
                    "sensors": {"soil_moisture": 24.0, "soil_temperature": 25.0},
                },
            ],
            "atmospheric_node": SAMPLE_TELEMETRY["data"]["atmospheric_node"],
        },
    },
    SAMPLE_TELEMETRY,
]

SAMPLE_ALERTS: List[Dict[str, Any]] = [
    {
        "hub_id": SAMPLE_TELEMETRY["hub_id"],
        "node_id": "soil-01",
        "message": "Soil moisture at soil-01 is critically low (24.5%)",
        "level": "critical",
        "created_at": "2025-10-22T13:30:00Z",
    }
]

SAMPLE_FORECAST: List[Dict[str, Any]] = [
    {
        "time": "2025-10-22T14:00:00Z",
        "temperature": 30.5,
        "precipitation": 0.0,
        "wind_speed": 2.2,
        "weather_code": 2,
    },
    {
        "time": "2025-10-22T17:00:00Z",
        "temperature": 28.9,
        "precipitation": 0.4,
        "wind_speed": 3.1,
        "weather_code": 80,
    },
]

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


def _safe_get(url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 5) -> Optional[Dict[str, Any]]:
    try:
        response = requests.get(url, params=params, timeout=timeout)
        if response.status_code == 200:
            return response.json()
    except Exception:
        return None
    return None


def fetch_latest_telemetry(api_base: Optional[str] = None, hub_id: Optional[str] = None) -> Dict[str, Any]:
    base = api_base or get_api_base()
    params = {"hub_id": hub_id} if hub_id else None
    payload = _safe_get(f"{base}/api/v1/data/latest", params=params)
    return payload or deepcopy(SAMPLE_TELEMETRY)


def fetch_history(api_base: Optional[str] = None, hub_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    base = api_base or get_api_base()
    params = {"hub_id": hub_id, "limit": limit} if hub_id else {"limit": limit}
    payload = _safe_get(f"{base}/api/v1/data/history", params=params)
    if payload and isinstance(payload, dict) and "items" in payload:
        return payload.get("items", [])
    return deepcopy(SAMPLE_HISTORY)


def fetch_alerts(api_base: Optional[str] = None, hub_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    base = api_base or get_api_base()
    params = {"hub_id": hub_id, "limit": limit} if hub_id else {"limit": limit}
    payload = _safe_get(f"{base}/api/v1/alerts", params=params)
    if payload and isinstance(payload, dict) and "items" in payload:
        return payload.get("items", [])
    return deepcopy(SAMPLE_ALERTS)


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
    payload = deepcopy(base_payload or SAMPLE_TELEMETRY)
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
        return deepcopy(SAMPLE_FORECAST)
    return deepcopy(SAMPLE_FORECAST)