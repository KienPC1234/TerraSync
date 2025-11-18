import requests
import logging
from typing import Dict, Any, Optional, List

# URL cơ sở của API server
API_BASE_URL = "http://127.0.0.1:8000"


logger = logging.getLogger(__name__)


class ApiClient:
    """
    Client để giao tiếp với TerraSync FastAPI server.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()

    def _get(
            self,
            endpoint: str,
            params: Optional[Dict[str,
                                  Any]] = None) -> Optional[Dict[str,
                                                                 Any]]:
        """Gửi yêu cầu GET đến API."""
        try:
            url = f"{self.base_url}{endpoint}"
            response = self.session.get(url, params=params, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Lỗi API GET tại {url}: {e}")
            return None

    def _post(
            self,
            endpoint: str,
            data: Dict[str,
                       Any]) -> Optional[Dict[str,
                                              Any]]:
        """Gửi yêu cầu POST đến API."""
        try:
            url = f"{self.base_url}{endpoint}"
            response = self.session.post(url, json=data, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Lỗi API POST tại {url}: {e}")
            return None

    def test_connection(self) -> bool:
        """Kiểm tra kết nối đến API."""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=3)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def register_hub(self, hub_data: Dict[str, Any]) -> bool:
        """Đăng ký một hub mới."""
        response_data = self._post("/api/v1/hub/register", data=hub_data)
        if response_data and response_data.get("status") == "success":
            return True
        logger.warning(
            f"Không thể đăng ký hub (có thể đã tồn tại): {response_data}")
        return False

    def get_hub_status(self, hub_id: str) -> List[Dict[str, Any]]:
        """Lấy trạng thái của một hub cụ thể."""
        params = {"hub_id": hub_id}
        response_data = self._get("/api/v1/hub/status", params=params)
        if response_data and response_data.get("status") == "success":
            return response_data.get("data", {}).get("hubs", [])
        return []

    def get_all_hub_statuses(self) -> List[Dict[str, Any]]:
        """Lấy trạng thái của tất cả các hub."""
        response_data = self._get("/api/v1/hub/status")
        if response_data and response_data.get("status") == "success":
            return response_data.get("data", {}).get("hubs", [])
        return []

    def get_latest_data(self, hub_id: str) -> Optional[Dict[str, Any]]:
        """Lấy dữ liệu telemetry mới nhất."""
        params = {"hub_id": hub_id}
        response_data = self._get("/api/v1/data/latest", params=params)
        if response_data and response_data.get("status") == "success":
            return response_data.get("data")
        return None

    def get_data_history(
            self,
            hub_id: str,
            limit: int = 50) -> Optional[Dict[str,
                                              Any]]:
        """Lấy lịch sử telemetry."""
        params = {"hub_id": hub_id, "limit": limit}
        response_data = self._get("/api/v1/data/history", params=params)
        if response_data and response_data.get("status") == "success":
            return response_data.get("data")
        return None

    def get_alerts(
            self,
            hub_id: str,
            limit: int = 50) -> Optional[Dict[str,
                                              Any]]:
        """Lấy các cảnh báo."""
        params = {"hub_id": hub_id, "limit": limit}
        response_data = self._get("/api/v1/alerts", params=params)
        if response_data and response_data.get("status") == "success":
            return response_data.get("data")
        return None


_client_instance: Optional[ApiClient] = None


def get_iot_client() -> ApiClient:
    """
    Khởi tạo và trả về một instance duy nhất của ApiClient (singleton pattern).
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = ApiClient(base_url=API_BASE_URL)
    return _client_instance


def test_iot_connection() -> bool:
    """Kiểm tra kết nối đến API."""
    client = get_iot_client()
    return client.test_connection()
