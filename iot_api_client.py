"""
TerraSync IoT API Client
Client để giao tiếp với IoT API từ Streamlit app
"""

import requests
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import streamlit as st

class TerraSyncIoTClient:
    """Client để giao tiếp với TerraSync IoT API"""
    
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = "terrasync-iot-2024"):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """Thực hiện HTTP request"""
        try:
            url = f"{self.base_url}{endpoint}"
            
            if method.upper() == "GET":
                response = requests.get(url, headers=self.headers, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(url, headers=self.headers, json=data, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.ConnectionError:
            st.error("❌ Không thể kết nối đến IoT API. Vui lòng kiểm tra server.")
            return None
        except requests.exceptions.Timeout:
            st.error("⏰ Timeout khi gọi IoT API.")
            return None
        except requests.exceptions.HTTPError as e:
            st.error(f"❌ Lỗi HTTP từ IoT API: {e}")
            return None
        except Exception as e:
            st.error(f"❌ Lỗi không xác định: {e}")
            return None
    
    def health_check(self) -> bool:
        """Kiểm tra trạng thái API"""
        result = self._make_request("GET", "/health")
        return result is not None and result.get("status") == "success"
    
    def get_latest_data(self, hub_id: Optional[str] = None) -> Optional[Dict]:
        """Lấy dữ liệu mới nhất"""
        endpoint = f"/api/v1/data/latest"
        if hub_id:
            endpoint += f"?hub_id={hub_id}"
        
        result = self._make_request("GET", endpoint)
        return result.get("data") if result else None
    
    def get_data_history(self, hub_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Lấy lịch sử dữ liệu"""
        endpoint = f"/api/v1/data/history?limit={limit}"
        if hub_id:
            endpoint += f"&hub_id={hub_id}"
        
        result = self._make_request("GET", endpoint)
        return result.get("data", {}).get("items", []) if result else []
    
    def get_alerts(self, hub_id: Optional[str] = None, limit: int = 50, level: Optional[str] = None) -> List[Dict]:
        """Lấy alerts"""
        endpoint = f"/api/v1/alerts?limit={limit}"
        if hub_id:
            endpoint += f"&hub_id={hub_id}"
        if level:
            endpoint += f"&level={level}"
        
        result = self._make_request("GET", endpoint)
        return result.get("data", {}).get("items", []) if result else []
    
    def get_hub_status(self, hub_id: Optional[str] = None) -> List[Dict]:
        """Lấy trạng thái hub"""
        endpoint = "/api/v1/hub/status"
        if hub_id:
            endpoint += f"?hub_id={hub_id}"
        
        result = self._make_request("GET", endpoint)
        return result.get("data", {}).get("hubs", []) if result else []
    
    def register_hub(self, hub_data: Dict) -> bool:
        """Đăng ký hub mới"""
        result = self._make_request("POST", "/api/v1/hub/register", hub_data)
        return result is not None and result.get("status") in ["success", "warning"]
    
    def register_sensor(self, sensor_data: Dict) -> bool:
        """Đăng ký sensor mới"""
        result = self._make_request("POST", "/api/v1/sensor/register", sensor_data)
        return result is not None and result.get("status") in ["success", "warning"]
    
    def send_telemetry_data(self, telemetry_data: Dict) -> bool:
        """Gửi dữ liệu telemetry"""
        result = self._make_request("POST", "/api/v1/data/ingest", telemetry_data)
        return result is not None and result.get("status") == "success"

# Global client instance
@st.cache_resource
def get_iot_client() -> TerraSyncIoTClient:
    """Lấy instance của IoT client (cached)"""
    return TerraSyncIoTClient()

def test_iot_connection() -> bool:
    """Test kết nối IoT API"""
    client = get_iot_client()
    return client.health_check()

def get_iot_data_for_user(user_email: str) -> Dict[str, Any]:
    """Lấy dữ liệu IoT cho user cụ thể"""
    client = get_iot_client()
    
    # Lấy tất cả hubs của user
    all_hubs = client.get_hub_status()
    user_hubs = [hub for hub in all_hubs if hub.get("hub", {}).get("user_email") == user_email]
    
    result = {
        "hubs": user_hubs,
        "latest_data": {},
        "alerts": [],
        "total_sensors": 0
    }
    
    # Lấy dữ liệu mới nhất cho mỗi hub
    for hub_info in user_hubs:
        hub_id = hub_info.get("hub", {}).get("hub_id")
        if hub_id:
            latest_data = client.get_latest_data(hub_id)
            if latest_data:
                result["latest_data"][hub_id] = latest_data
            
            # Lấy alerts cho hub
            hub_alerts = client.get_alerts(hub_id, limit=10)
            result["alerts"].extend(hub_alerts)
            
            # Đếm sensors
            result["total_sensors"] += hub_info.get("sensor_count", 0)
    
    # Sắp xếp alerts theo thời gian
    result["alerts"].sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return result

def create_sample_telemetry_data(hub_id: str, lat: float, lon: float) -> Dict:
    """Tạo dữ liệu telemetry mẫu"""
    return {
        "hub_id": hub_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "location": {
            "lat": lat,
            "lon": lon
        },
        "data": {
            "soil_nodes": [
                {
                    "node_id": "soil-01",
                    "sensors": {
                        "soil_moisture": 35.2,
                        "soil_temperature": 28.5
                    }
                },
                {
                    "node_id": "soil-02",
                    "sensors": {
                        "soil_moisture": 42.1,
                        "soil_temperature": 27.8
                    }
                }
            ],
            "atmospheric_node": {
                "node_id": "atm-01",
                "sensors": {
                    "air_temperature": 31.2,
                    "air_humidity": 68.5,
                    "rain_intensity": 0,
                    "wind_speed": 2.3,
                    "light_intensity": 850,
                    "barometric_pressure": 1008.2
                }
            }
        }
    }

def create_sample_hub_data(hub_id: str, user_email: str, field_id: str, lat: float, lon: float) -> Dict:
    """Tạo dữ liệu hub mẫu"""
    return {
        "hub_id": hub_id,
        "user_email": user_email,
        "location": {
            "lat": lat,
            "lon": lon
        },
        "description": f"IoT Hub for Field {field_id}",
        "field_id": field_id
    }

def create_sample_sensor_data(hub_id: str, node_id: str, sensor_type: str, lat: float, lon: float) -> Dict:
    """Tạo dữ liệu sensor mẫu"""
    return {
        "hub_id": hub_id,
        "node_id": node_id,
        "sensor_type": sensor_type,
        "location": {
            "lat": lat,
            "lon": lon
        },
        "description": f"{sensor_type.title()} sensor {node_id}"
    }
