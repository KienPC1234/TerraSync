import os
import requests
import pandas as pd
import google.generativeai as genai
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


def fetch_forecast(lat: float, lon: float) -> Optional[Dict[str, pd.DataFrame]]:
    """
    Lấy dự báo thời tiết chi tiết (hàng giờ và hàng ngày) từ Open-Meteo API.
    """
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,apparent_temperature,precipitation,relative_humidity_2m,surface_pressure,wind_speed_10m,wind_direction_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,wind_direction_10m_dominant",
            "timezone": "auto",
            "forecast_days": 7
        }
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()

        # Process hourly data
        hourly_df = pd.DataFrame(data['hourly'])
        hourly_df['time'] = pd.to_datetime(hourly_df['time'])
        
        # Process daily data
        daily_df = pd.DataFrame(data['daily'])
        daily_df['time'] = pd.to_datetime(daily_df['time'])

        return {"hourly": hourly_df, "daily": daily_df}

    except Exception as e:
        print(f"Lỗi khi lấy dữ liệu thời tiết: {e}")
        return None


def get_weather_recommendation(field_data: Dict[str, Any], weather_data: Dict[str, pd.DataFrame]) -> str:
    """
    Sử dụng Gemini để tạo khuyến nghị dựa trên dữ liệu thời tiết và cây trồng.
    """
    try:
        # It's better to configure the API key once at the app's entry point
        # For example, in streamlit_app.py using st.secrets
        # genai.configure(api_key=st.secrets["google_api_key"])
        
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            generation_config=genai.types.GenerationConfig(
                temperature=0.6, top_p=0.9
            )
        )

        daily_weather_summary = weather_data['daily'].to_markdown(index=False)
        
        prompt = f"""
        Bạn là một chuyên gia nông học và khí tượng học của Việt Nam, tên là CropNet AI.
        Nhiệm vụ của bạn là đưa ra lời khuyên canh tác chi tiết, chuyên nghiệp và hữu ích bằng tiếng Việt.

        **DỮ LIỆU ĐẦU VÀO:**

        1.  **Thông tin Vườn:**
            -   Tên vườn: {field_data.get('name', 'N/A')}
            -   Loại cây trồng: {field_data.get('crop', 'N/A')}
            -   Giai đoạn sinh trưởng hiện tại: {field_data.get('stage', 'N/A')}

        2.  **Dự báo thời tiết 7 ngày tới (dạng bảng Markdown):**
        {daily_weather_summary}

        **YÊU CẦU:**

        Dựa vào các dữ liệu trên, hãy đưa ra một bản tin khuyến nghị chi tiết cho người nông dân. Phân tích các yếu tố sau:

        1.  **Phân tích tưới tiêu:**
            -   Dựa vào `precipitation_sum` (tổng lượng mưa) và `temperature_2m_max` (nhiệt độ tối đa).
            -   Đưa ra lịch tưới khuyến nghị cho từng ngày hoặc một khoảng thời gian (ví dụ: "3 ngày tới không cần tưới do mưa", "Ngày X và Y cần tưới bổ sung do nắng nóng").
            -   Chỉ rõ ngày nào nên tưới, ngày nào không.

        2.  **Rủi ro sâu bệnh:**
            -   Phân tích nguy cơ bùng phát sâu bệnh dựa trên thời tiết (ví dụ: độ ẩm cao, mưa nhiều có thể gây bệnh nấm; thời tiết khô nóng có thể bùng phát nhện đỏ).
            -   Đề xuất các biện pháp phòng ngừa hoặc kiểm tra (ví dụ: "Kiểm tra mặt dưới lá vào các ngày nắng nóng", "Sau các trận mưa, cần phun phòng nấm...").

        3.  **Hành động khác:**
            -   Đề cập đến các ảnh hưởng của gió (`wind_speed_10m_max`) nếu có (ví dụ: cây có thể bị đổ, cần chằng chống).
            -   Đưa ra các lời khuyên chung khác nếu có.

        **ĐỊNH DẠNG ĐẦU RA:**
        -   Sử dụng Markdown.
        -   Sử dụng tiêu đề, danh sách (bullet points) và in đậm để dễ đọc.
        -   Sử dụng các emoji (💧, ☀️, 🐛, 🌬️) để làm cho bản tin sinh động.
        -   Giọng văn chuyên nghiệp nhưng gần gũi, dễ hiểu.
        """
        
        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        error_message = f"Lỗi khi tạo khuyến nghị từ AI: {e}. Vui lòng kiểm tra cấu hình GOOGLE_API_KEY."
        print(error_message)
        return f"⚠️ {error_message}"


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


def calculate_days_to_harvest(field: Dict[str, Any]) -> Optional[int]:
    """
    Tính toán số ngày còn lại để thu hoạch dựa trên thông tin của vườn.
    """
    crop_name = field.get("crop")
    created_at_str = field.get("created_at")
    creation_stage = field.get("stage")

    if not all([crop_name, created_at_str, creation_stage]):
        return None

    # Lấy thông tin cây trồng từ crop_db
    all_crops = crop_db.get("crops", [])
    crop_info = next((c for c in all_crops if c.get("name") == crop_name), None)
    if not crop_info or "growth_stages" not in crop_info:
        return None

    # Tính tổng thời gian sinh trưởng
    total_duration = sum(crop_info["growth_stages"].values())

    # Tính số ngày đã trôi qua kể từ khi vườn được tạo (ở một giai đoạn nhất định)
    try:
        # Chuyển chuỗi ISO 8601 thành đối tượng datetime
        created_at = datetime.fromisoformat(created_at_str)
        # Nếu `created_at` có timezone, so sánh với `now()` có cùng timezone
        if created_at.tzinfo:
            now = datetime.now(created_at.tzinfo)
        else:
            # Ngược lại, so sánh với `now()` naive
            now = datetime.now()
        days_passed_since_creation = (now - created_at).days
    except (ValueError, TypeError):
        return None  # Trả về None nếu định dạng ngày tháng không hợp lệ

    # Xác định số ngày của các giai đoạn trước giai đoạn lúc tạo
    stages_order = ['initial', 'development', 'mid_season', 'late_season']
    if creation_stage not in stages_order:
        return None

    creation_stage_index = stages_order.index(creation_stage)
    days_in_previous_stages = 0
    for i in range(creation_stage_index):
        stage_key = stages_order[i]
        days_in_previous_stages += crop_info["growth_stages"].get(stage_key, 0)

    # Tổng số ngày đã trôi qua từ lúc gieo trồng giả định
    total_days_passed = days_in_previous_stages + days_passed_since_creation

    days_to_harvest = total_duration - total_days_passed

    return max(0, days_to_harvest)