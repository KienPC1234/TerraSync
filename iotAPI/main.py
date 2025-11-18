from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import os
import sys
import logging

from fastapi import FastAPI, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
# Cần cài đặt: pip install fastapi-utils
from fastapi_utils.tasks import repeat_every

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from database import db
except ImportError:
    logger.error("Không thể tìm thấy module 'database'. Đảm bảo nó tồn tại.")
    # Tạo một đối tượng db giả để code không bị lỗi khi chạy

    class MockDB:
        def add(self, *args):
            logger.warning("DB: Chế độ giả lập, không lưu add.")

        def get(self, *args, **kwargs):
            logger.warning("DB: Chế độ giả lập, trả về []")
            return []

        def overwrite_table(self, *args):
            logger.warning("DB: Chế độ giả lập, không lưu overwrite.")
    db = MockDB()


# --- Pydantic Models (Không thay đổi) ---
class SoilSensors(BaseModel):
    soil_moisture: float = Field(
        ..., ge=0, le=100, description="Soil moisture percentage")
    soil_temperature: float = Field(
        ..., description="Soil temperature in Celsius")


class SoilNode(BaseModel):
    node_id: str = Field(..., description="Unique node identifier")
    sensors: SoilSensors


class AtmosphericSensors(BaseModel):
    air_temperature: float = Field(
        ..., description="Air temperature in Celsius")
    air_humidity: float = Field(
        ..., ge=0, le=100, description="Air humidity percentage")
    rain_intensity: float = Field(
        ..., ge=0, description="Rain intensity in mm/h")
    wind_speed: float = Field(..., ge=0, description="Wind speed in m/s")
    light_intensity: float = Field(
        ..., ge=0, description="Light intensity in Lux")
    barometric_pressure: float = Field(
        ..., ge=0, description="Barometric pressure in hPa")


class AtmosphericNode(BaseModel):
    node_id: str = Field(..., description="Unique atmospheric node identifier")
    sensors: AtmosphericSensors


class TelemetryData(BaseModel):
    soil_nodes: List[SoilNode] = Field(
        ..., description="List of soil sensor nodes")
    atmospheric_node: AtmosphericNode = Field(
        ..., description="Atmospheric sensor node")


class TelemetryPayload(BaseModel):
    hub_id: str = Field(..., description="Unique hub identifier")
    timestamp: datetime = Field(..., description="Timestamp of data collection")
    location: Optional[Dict[str, float]] = Field(
        None, description="Optional location coordinates")
    data: TelemetryData = Field(..., description="Sensor data")

    @field_validator("timestamp", mode="before")
    def parse_timestamp(cls, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                if value.endswith("Z"):
                    value = value.replace("Z", "+00:00")
                return datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("Invalid timestamp format") from exc
        raise ValueError("timestamp must be datetime or ISO 8601 string")


class AlertRecord(BaseModel):
    hub_id: str
    node_id: Optional[str]
    message: str
    level: str = Field(..., pattern="^(info|warning|critical)$")
    created_at: datetime


class HubRegistration(BaseModel):
    hub_id: str = Field(..., description="Unique hub identifier")
    user_email: str = Field(..., description="User email who owns this hub")
    field_id: str = Field(..., description="Associated field ID")
    name: Optional[str] = Field(None, description="User-friendly hub name")
    # Đã sửa lỗi thiếu trường 'location' và 'description' so với logic endpoint
    location: Optional[Dict[str, float]] = Field(None)
    description: Optional[str] = Field(None)


class SensorRegistration(BaseModel):
    hub_id: str = Field(..., description="Hub identifier")
    node_id: str = Field(..., description="Node identifier")
    sensor_type: str = Field(
        ...,
        pattern="^(soil|atmospheric)$",
        description="Type of sensor")
    location: Optional[Dict[str, float]] = Field(
        None, description="Sensor location")
    description: Optional[str] = Field(None, description="Sensor description")


class APIResponse(BaseModel):
    status: str = Field(..., description="Response status")
    message: Optional[str] = Field(None, description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")


# --- Khởi tạo FastAPI ---
app = FastAPI(
    title="TerraSync IoT API",
    version="1.2.0 (Unlimited Telemetry)",
    description="IoT data ingestion and management API for TerraSync "
    "smart farming system",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Trong production, hãy chỉ định rõ origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Cấu hình dọn dẹp tự động (Không thay đổi) ---
ALERT_RETENTION_DAYS = 30
TELEMETRY_RETENTION_DAYS = 90  # Thêm hằng số mới cho dọn dẹp Telemetry


@app.on_event("startup")
@repeat_every(seconds=60 * 60 * 24)  # Chạy mỗi 24 giờ
async def cleanup_old_data():
    """Tự động dọn dẹp các cảnh báo VÀ telemetry cũ"""

    # 1. Dọn dẹp Alerts
    logger.info("Đang chạy tác vụ dọn dẹp Alert...")
    try:
        all_alerts = db.get("alerts")
        if not all_alerts:
            logger.info("Không có Alert nào để dọn dẹp.")
        else:
            cutoff_date = datetime.now(
                timezone.utc) - timedelta(days=ALERT_RETENTION_DAYS)
            fresh_alerts = []
            for alert in all_alerts:
                created_at_str = alert.get("created_at")
                if isinstance(created_at_str, str):
                    try:
                        alert_time = datetime.fromisoformat(created_at_str)
                        if alert_time > cutoff_date:
                            fresh_alerts.append(alert)
                    except ValueError:
                        fresh_alerts.append(alert)  # Giữ lại nếu không thể parse
                else:
                    fresh_alerts.append(alert)  # Giữ lại nếu định dạng lạ

            if len(fresh_alerts) < len(all_alerts):
                db.overwrite_table("alerts", fresh_alerts)
                logger.info(
                    f"Đã dọn dẹp {len(all_alerts) - len(fresh_alerts)} "
                    "alert cũ.")
            else:
                logger.info("Không có alert cũ nào cần dọn dẹp.")
    except Exception as e:
        logger.error(f"Lỗi khi dọn dẹp alert: {e}")

    # 2. Dọn dẹp Telemetry
    logger.info("Đang chạy tác vụ dọn dẹp Telemetry...")
    try:
        all_telemetry = db.get("telemetry")
        if not all_telemetry:
            logger.info("Không có Telemetry nào để dọn dẹp.")
            return

        cutoff_date = datetime.now(
            timezone.utc) - timedelta(days=TELEMETRY_RETENTION_DAYS)
        fresh_telemetry = []
        for record in all_telemetry:
            timestamp_str = record.get("timestamp")
            if isinstance(timestamp_str, str):
                try:
                    record_time = datetime.fromisoformat(timestamp_str)
                    if record_time > cutoff_date:
                        fresh_telemetry.append(record)
                except ValueError:
                    fresh_telemetry.append(record)  # Giữ lại nếu không thể parse
            else:
                fresh_telemetry.append(record)  # Giữ lại nếu định dạng lạ

        if len(fresh_telemetry) < len(all_telemetry):
            db.overwrite_table("telemetry", fresh_telemetry)
            logger.info(
                f"Đã dọn dẹp {len(all_telemetry) - len(fresh_telemetry)} "
                "bản ghi telemetry cũ.")
        else:
            logger.info("Không có telemetry cũ nào cần dọn dẹp.")

    except Exception as e:
        logger.error(f"Lỗi khi dọn dẹp telemetry: {e}")


# --- Logic nghiệp vụ (Tách riêng) ---

# --- ĐÃ SỬA: Thêm nhiều alert 'critical' hơn ---
def evaluate_alerts(payload: TelemetryPayload) -> List[AlertRecord]:
    """Phân tích dữ liệu cảm biến và tạo cảnh báo (ĐÃ SỬA)"""
    alerts: List[AlertRecord] = []
    current_time = datetime.now(timezone.utc)

    # === Soil Alerts ===
    for node in payload.data.soil_nodes:
        moisture = node.sensors.soil_moisture
        temperature = node.sensors.soil_temperature

        # --- Soil Moisture ---
        if moisture < 20:  # Mức 1: Critical
            alerts.append(
                AlertRecord(
                    hub_id=payload.hub_id,
                    node_id=node.node_id,
                    message=f"🚨 KHẨN CẤP: Độ ẩm đất tại {node.node_id} "
                    f"CỰC THẤP ({moisture:.1f}%) - Yêu cầu tưới "
                    "NGAY LẬP TỨC!",
                    level="critical",
                    created_at=current_time))
        elif moisture < 30:  # Mức 2: Warning
            alerts.append(
                AlertRecord(
                    hub_id=payload.hub_id,
                    node_id=node.node_id,
                    message=f"⚠️ Cảnh báo: Độ ẩm đất tại {node.node_id} "
                    f"đang ở mức thấp ({moisture:.1f}%) - Lên kế hoạch tưới",
                    level="warning",
                    created_at=current_time))
        elif moisture > 90:  # Sửa từ 85 -> 90
            alerts.append(
                AlertRecord(
                    hub_id=payload.hub_id,
                    node_id=node.node_id,
                    message=f"💧 Thông tin: Đất tại {node.node_id} rất ẩm "
                    f"({moisture:.1f}%) - Nguy cơ ngập úng",
                    level="info",
                    created_at=current_time))

        # --- Soil Temperature ---
        if temperature > 50:  # Mức 1: Critical (Rất nóng)
            alerts.append(
                AlertRecord(
                    hub_id=payload.hub_id,
                    node_id=node.node_id,
                    message=f"🚨 KHẨN CẤP: Nhiệt độ đất tại {node.node_id} "
                    f"CỰC CAO ({temperature:.1f}°C) - Nguy cơ hỏng rễ!",
                    level="critical",
                    created_at=current_time))
        elif temperature > 40:  # Mức 2: Warning (Nóng)
            alerts.append(
                AlertRecord(
                    hub_id=payload.hub_id,
                    node_id=node.node_id,
                    message=f"🌡️ Cảnh báo: Nhiệt độ đất tại {node.node_id} "
                    f"cao ({temperature:.1f}°C) - Kiểm tra stress nhiệt",
                    level="warning",
                    created_at=current_time))
        elif temperature < 0:  # Mức 3: Critical (Đóng băng)
            alerts.append(
                AlertRecord(
                    hub_id=payload.hub_id,
                    node_id=node.node_id,
                    message=f"🚨 KHẨN CẤP: Nhiệt độ đất tại {node.node_id} "
                    f"DƯỚI 0°C ({temperature:.1f}°C) - Nguy cơ đóng băng!",
                    level="critical",
                    created_at=current_time))
        elif temperature < 5:  # Mức 4: Warning (Lạnh)
            alerts.append(
                AlertRecord(
                    hub_id=payload.hub_id,
                    node_id=node.node_id,
                    message=f"❄️ Cảnh báo: Nhiệt độ đất tại {node.node_id} "
                    f"rất thấp ({temperature:.1f}°C) - Kiểm tra sương giá",
                    level="warning",
                    created_at=current_time))

    # === Atmospheric Alerts ===
    atm = payload.data.atmospheric_node.sensors
    atm_node_id = payload.data.atmospheric_node.node_id

    # --- Wind Speed ---
    if atm.wind_speed > 25:  # Mức 1: Critical (Bão)
        alerts.append(
            AlertRecord(
                hub_id=payload.hub_id,
                node_id=atm_node_id,
                message=f"🚨 KHẨN CẤP: Gió CỰC MẠNH ({atm.wind_speed:.1f} m/s) "
                "- Nguy cơ bão, gãy đổ!",
                level="critical",
                created_at=current_time))
    elif atm.wind_speed > 15:  # Mức 2: Warning (Gió to)
        alerts.append(
            AlertRecord(
                hub_id=payload.hub_id,
                node_id=atm_node_id,
                message=f"💨 Cảnh báo: Gió mạnh ({atm.wind_speed:.1f} m/s) "
                "- Cân nhắc gia cố",
                level="warning",
                created_at=current_time))

    # --- Rain Intensity ---
    if atm.rain_intensity > 50:  # Mức 1: Critical (Lũ lụt)
        alerts.append(
            AlertRecord(
                hub_id=payload.hub_id,
                node_id=atm_node_id,
                message=f"🚨 KHẨN CẤP: Mưa CỰC LỚN "
                f"({atm.rain_intensity:.1f} mm/h) - Nguy cơ lũ lụt!",
                level="critical",
                created_at=current_time))
    elif atm.rain_intensity > 10:  # Mức 2: Info (Mưa to)
        alerts.append(
            AlertRecord(
                hub_id=payload.hub_id,
                node_id=atm_node_id,
                message=f"🌧️ Thông tin: Đang mưa to "
                f"({atm.rain_intensity:.1f} mm/h) - Dừng tưới",
                level="info",
                created_at=current_time))

    # --- Air Temperature (MỚI) ---
    if atm.air_temperature > 45:  # Mức 1: Critical (Nắng nóng gay gắt)
        alerts.append(
            AlertRecord(
                hub_id=payload.hub_id,
                node_id=atm_node_id,
                message=f"🚨 KHẨN CẤP: Nhiệt độ không khí CỰC CAO "
                f"({atm.air_temperature:.1f}°C) - Nguy cơ sốc nhiệt!",
                level="critical",
                created_at=current_time))
    elif atm.air_temperature < 0:  # Mức 2: Critical (Băng giá)
        alerts.append(
            AlertRecord(
                hub_id=payload.hub_id,
                node_id=atm_node_id,
                message=f"🚨 KHẨN CẤP: Nhiệt độ không khí DƯỚI 0°C "
                f"({atm.air_temperature:.1f}°C) - Nguy cơ băng giá!",
                level="critical",
                created_at=current_time))

    # --- Humidity ---
    if atm.air_humidity > 95:  # Sửa từ 90 -> 95
        alerts.append(
            AlertRecord(
                hub_id=payload.hub_id,
                node_id=atm_node_id,
                message=f"💧 Thông tin: Độ ẩm không khí rất cao "
                f"({atm.air_humidity:.1f}%) - Nguy cơ nấm mốc",
                level="info",
                created_at=current_time))

    return alerts
# --- KẾT THÚC SỬA 1 ---


def store_alert(alert: AlertRecord) -> None:
    """Lưu alert vào database"""
    db.add(
        "alerts",
        {
            "hub_id": alert.hub_id,
            "node_id": alert.node_id,
            "message": alert.message,
            "level": alert.level,
            "created_at": alert.created_at.isoformat(),
        },
    )


def serialize_payload(payload: TelemetryPayload) -> Dict[str, Any]:
    """Chuẩn bị payload để lưu vào DB"""
    body = payload.dict()
    body["timestamp"] = payload.timestamp.replace(
        tzinfo=timezone.utc).isoformat()
    return body


# --- ĐÃ SỬA: Bỏ giới hạn, chỉ thêm telemetry mới ---
def process_telemetry(payload: TelemetryPayload):
    """
    Hàm này được chạy trong background task.
    (ĐÃ SỬA: Bỏ giới hạn, chỉ thêm telemetry mới)
    """
    try:
        # 1. Chuẩn bị bản ghi mới
        new_record = serialize_payload(payload)

        # 2. Thêm thẳng bản ghi mới vào DB
        # Không cần get_all, không cần overwrite_table để giới hạn
        db.add("telemetry", new_record)

        # 3. Phân tích và lưu trữ alerts (như cũ)
        alerts = evaluate_alerts(payload)
        for alert in alerts:
            store_alert(alert)

        logger.info(
            f"Đã xử lý xong telemetry cho hub {payload.hub_id} "
            f"(thêm mới). Tạo {len(alerts)} alerts.")
    except Exception as e:
        logger.error(
            f"Lỗi background task khi xử lý hub {payload.hub_id}: {e}")
# --- KẾT THÚC SỬA 2 ---


# --- API Endpoints (Không thay đổi) ---

@app.get("/", response_model=APIResponse)
async def root():
    """Root endpoint với thông tin API"""
    return APIResponse(
        status="success",
        message="TerraSync IoT API v1.2.0 - Smart Farming Data Ingestion",
        data={
            "version": "1.2.0",
            "endpoints": {
                "data_ingest": "/api/v1/data/ingest",
                "data_latest": "/api/v1/data/latest",
                "data_history": "/api/v1/data/history",
                "alerts": "/api/v1/alerts",
                "hub_register": "/api/v1/hub/register",
                "sensor_register": "/api/v1/sensor/register",
                "hub_status": "/api/v1/hub/status"
            }
        }
    )


@app.post("/api/v1/data/ingest", response_model=APIResponse)
async def ingest_telemetry_data(
    payload: TelemetryPayload,
    background_tasks: BackgroundTasks
) -> APIResponse:
    """
    Tiếp nhận dữ liệu telemetry từ IoT hub.
    Xử lý lưu trữ và phân tích trong nền.
    """
    try:
        # Thêm tác vụ vào hàng đợi và trả về ngay lập tức
        background_tasks.add_task(process_telemetry, payload)

        return APIResponse(
            status="success",
            message="Data ingestion accepted. Processing in background.",
            data={
                "hub_id": payload.hub_id,
                "received_at": datetime.now(timezone.utc).isoformat()
            }
        )
    except Exception as e:
        # Lỗi này hiếm khi xảy ra, trừ khi payload không hợp lệ
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to queue data ingestion: {str(e)}"
        )


@app.get("/api/v1/data/latest", response_model=APIResponse)
async def get_latest_data(
    hub_id: Optional[str] = None
) -> APIResponse:
    """Lấy dữ liệu telemetry mới nhất (tối ưu hóa)"""
    try:
        # Tối ưu: Lọc ở phía DB
        query = {"hub_id": hub_id} if hub_id else {}
        records = db.get("telemetry", query)

        if not records:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No telemetry data available for this query"
            )

        # Sắp xếp bằng Python (Nên tối ưu ở DB nếu có thể)
        records.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
        latest_record = records[0]

        return APIResponse(
            status="success",
            message="Latest data retrieved successfully",
            data=latest_record
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve data: {str(e)}"
        )


@app.get("/api/v1/data/history", response_model=APIResponse)
async def get_data_history(
    hub_id: Optional[str] = None,
    limit: int = 50
) -> APIResponse:
    """Lấy lịch sử telemetry (tối ưu hóa)"""
    try:
        # Tối ưu: Lọc ở phía DB
        query = {"hub_id": hub_id} if hub_id else {}
        records = db.get("telemetry", query)

        # Sắp xếp và giới hạn (Nên tối ưu ở DB nếu có thể)
        records.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
        total_count = len(records)
        limited_records = records[:limit]

        return APIResponse(
            status="success",
            message=f"Retrieved {len(limited_records)} historical records",
            data={
                "items": limited_records,
                "total_count": total_count,
                "returned_count": len(limited_records)
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve history: {str(e)}"
        )


@app.get("/api/v1/alerts", response_model=APIResponse)
async def get_alerts(
    hub_id: Optional[str] = None,
    limit: int = 50,
    level: Optional[str] = None
) -> APIResponse:
    """Lấy alerts (tối ưu hóa)"""
    try:
        # Tối ưu: Xây dựng bộ lọc và truy vấn 1 lần
        query = {}
        if hub_id:
            query["hub_id"] = hub_id
        if level:
            query["level"] = level

        records = db.get("alerts", query)

        # Sắp xếp và giới hạn (Nên tối ưu ở DB nếu có thể)
        records.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        total_count = len(records)
        limited_records = records[:limit]

        return APIResponse(
            status="success",
            message=f"Retrieved {len(limited_records)} alerts",
            data={
                "items": limited_records,
                "total_count": total_count,
                "returned_count": len(limited_records)
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve alerts: {str(e)}"
        )


@app.post("/api/v1/hub/register", response_model=APIResponse)
async def register_hub(
    hub_data: HubRegistration
) -> APIResponse:
    """Đăng ký một IoT hub mới"""
    try:
        existing_hubs = db.get("iot_hubs", {"hub_id": hub_data.hub_id})
        if existing_hubs:
            return APIResponse(
                status="warning",
                message="Hub already registered",
                data={"hub_id": hub_data.hub_id}
            )

        hub_record = {
            "hub_id": hub_data.hub_id,
            "user_email": hub_data.user_email,
            "location": hub_data.location,
            "description": hub_data.description,
            "field_id": hub_data.field_id,
            "name": hub_data.name,  # Đã thêm trường name
            "status": "active",
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "last_seen": None  # Khởi tạo là None
        }

        db.add("iot_hubs", hub_record)

        return APIResponse(
            status="success",
            message="Hub registered successfully",
            data={"hub_id": hub_data.hub_id}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register hub: {str(e)}"
        )


@app.post("/api/v1/sensor/register", response_model=APIResponse)
async def register_sensor(
    sensor_data: SensorRegistration
) -> APIResponse:
    """Đăng ký một node cảm biến mới"""
    try:
        existing_sensors = db.get("sensors", {"node_id": sensor_data.node_id})
        if existing_sensors:
            return APIResponse(
                status="warning",
                message="Sensor already registered",
                data={"node_id": sensor_data.node_id}
            )

        sensor_record = {
            "hub_id": sensor_data.hub_id,
            "node_id": sensor_data.node_id,
            "sensor_type": sensor_data.sensor_type,
            "location": sensor_data.location,
            "description": sensor_data.description,
            "status": "active",
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "last_seen": None  # Khởi tạo là None
        }

        db.add("sensors", sensor_record)

        return APIResponse(
            status="success",
            message="Sensor registered successfully",
            data={"node_id": sensor_data.node_id}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register sensor: {str(e)}"
        )


@app.get("/api/v1/hub/status", response_model=APIResponse)
async def get_hub_status(
    hub_id: Optional[str] = None
) -> APIResponse:
    """Lấy trạng thái hub và các cảm biến (tối ưu hóa)"""
    try:
        # Lọc trước khi lấy
        hub_query = {"hub_id": hub_id} if hub_id else {}
        sensor_query = {"hub_id": hub_id} if hub_id else {}
        telemetry_query = {"hub_id": hub_id} if hub_id else {}

        hubs = db.get("iot_hubs", hub_query)
        sensors = db.get("sensors", sensor_query)
        telemetry = db.get("telemetry", telemetry_query)

        # Nhóm theo hub_id để tăng tốc
        sensors_by_hub = {}
        for s in sensors:
            sensors_by_hub.setdefault(s.get("hub_id"), []).append(s)

        latest_telemetry_by_hub = {}
        telemetry.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        for t in telemetry:
            h_id = t.get("hub_id")
            if h_id not in latest_telemetry_by_hub:
                latest_telemetry_by_hub[h_id] = t

        hub_status = []
        for hub in hubs:
            hub_id_key = hub.get("hub_id")
            hub_sensors = sensors_by_hub.get(hub_id_key, [])
            latest_telemetry = latest_telemetry_by_hub.get(hub_id_key)

            hub_status.append({
                "hub": hub,
                "sensors": hub_sensors,
                "sensor_count": len(hub_sensors),
                "latest_telemetry": latest_telemetry,
                "last_data_time": latest_telemetry.get("timestamp")
                if latest_telemetry else None
            })

        return APIResponse(
            status="success",
            message=f"Retrieved status for {len(hub_status)} hubs",
            data={"hubs": hub_status}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve hub status: {str(e)}"
        )

# Health check endpoint


@app.get("/health", response_model=APIResponse)
async def health_check():
    """Endpoint kiểm tra sức khỏe"""
    return APIResponse(
        status="success",
        message="TerraSync IoT API is healthy",
        data={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": "connected"  # Giả định là đã kết nối
        }
    )


if __name__ == "__main__":
    import uvicorn
    # Cần cài đặt: pip install uvicorn[standard]
    uvicorn.run(app, host="0.0.0.0", port=8000)