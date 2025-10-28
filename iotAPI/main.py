from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json
import os
import sys

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import db

# Security
security = HTTPBearer()


class SoilSensors(BaseModel):
    soil_moisture: float = Field(..., ge=0, le=100, description="Soil moisture percentage")
    soil_temperature: float = Field(..., description="Soil temperature in Celsius")

class SoilNode(BaseModel):
    node_id: str = Field(..., description="Unique node identifier")
    sensors: SoilSensors

class AtmosphericSensors(BaseModel):
    air_temperature: float = Field(..., description="Air temperature in Celsius")
    air_humidity: float = Field(..., ge=0, le=100, description="Air humidity percentage")
    rain_intensity: float = Field(..., ge=0, description="Rain intensity in mm/h")
    wind_speed: float = Field(..., ge=0, description="Wind speed in m/s")
    light_intensity: float = Field(..., ge=0, description="Light intensity in Lux")
    barometric_pressure: float = Field(..., ge=0, description="Barometric pressure in hPa")

class AtmosphericNode(BaseModel):
    node_id: str = Field(..., description="Unique atmospheric node identifier")
    sensors: AtmosphericSensors

class TelemetryData(BaseModel):
    soil_nodes: List[SoilNode] = Field(..., description="List of soil sensor nodes")
    atmospheric_node: AtmosphericNode = Field(..., description="Atmospheric sensor node")

class TelemetryPayload(BaseModel):
    hub_id: str = Field(..., description="Unique hub identifier")
    timestamp: datetime = Field(..., description="Timestamp of data collection")
    location: Optional[Dict[str, float]] = Field(None, description="Optional location coordinates")
    data: TelemetryData = Field(..., description="Sensor data")

    @validator("timestamp", pre=True)
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
    level: str = Field(..., regex="^(info|warning|critical)$")
    created_at: datetime

class HubRegistration(BaseModel):
    hub_id: str = Field(..., description="Unique hub identifier")
    user_email: str = Field(..., description="User email who owns this hub")
    location: Optional[Dict[str, float]] = Field(None, description="Hub location coordinates")
    description: Optional[str] = Field(None, description="Hub description")
    field_id: Optional[str] = Field(None, description="Associated field ID")

class SensorRegistration(BaseModel):
    hub_id: str = Field(..., description="Hub identifier")
    node_id: str = Field(..., description="Node identifier")
    sensor_type: str = Field(..., regex="^(soil|atmospheric)$", description="Type of sensor")
    location: Optional[Dict[str, float]] = Field(None, description="Sensor location")
    description: Optional[str] = Field(None, description="Sensor description")

class APIResponse(BaseModel):
    status: str = Field(..., description="Response status")
    message: Optional[str] = Field(None, description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")



# Simple API key validation (in production, use proper authentication)
API_KEYS = {
    "terrasync-iot-2024": "default",
    "hub-master-key": "hub-access"
}

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key for IoT hub access"""
    if credentials.credentials not in API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return credentials.credentials

# FastAPI app
app = FastAPI(
    title="TerraSync IoT API",
    version="1.0.0",
    description="IoT data ingestion and management API for TerraSync smart farming system",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def evaluate_alerts(payload: TelemetryPayload) -> List[AlertRecord]:
    """Evaluate sensor data and generate alerts"""
    alerts: List[AlertRecord] = []
    current_time = datetime.now(timezone.utc)
    
    # Soil moisture alerts
    for node in payload.data.soil_nodes:
        moisture = node.sensors.soil_moisture
        temperature = node.sensors.soil_temperature
        
        if moisture < 20:
            alerts.append(
                AlertRecord(
                    hub_id=payload.hub_id,
                    node_id=node.node_id,
                    message=f"🚨 Critical: Soil moisture at {node.node_id} is extremely low ({moisture:.1f}%) - Immediate irrigation needed!",
                    level="critical",
                    created_at=current_time,
                )
            )
        elif moisture < 30:
            alerts.append(
                AlertRecord(
                    hub_id=payload.hub_id,
                    node_id=node.node_id,
                    message=f"⚠️ Warning: Soil moisture at {node.node_id} is low ({moisture:.1f}%) - Consider irrigation",
                    level="warning",
                    created_at=current_time,
                )
            )
        elif moisture > 85:
            alerts.append(
                AlertRecord(
                    hub_id=payload.hub_id,
                    node_id=node.node_id,
                    message=f"💧 Info: Soil moisture at {node.node_id} is high ({moisture:.1f}%) - Reduce irrigation",
                    level="info",
                    created_at=current_time,
                )
            )
        
        # Soil temperature alerts
        if temperature > 40:
            alerts.append(
                AlertRecord(
                    hub_id=payload.hub_id,
                    node_id=node.node_id,
                    message=f"🌡️ Warning: Soil temperature at {node.node_id} is very high ({temperature:.1f}°C) - Check for heat stress",
                    level="warning",
                    created_at=current_time,
                )
            )
        elif temperature < 5:
            alerts.append(
                AlertRecord(
                    hub_id=payload.hub_id,
                    node_id=node.node_id,
                    message=f"❄️ Warning: Soil temperature at {node.node_id} is very low ({temperature:.1f}°C) - Check for frost damage",
                    level="warning",
                    created_at=current_time,
                )
            )
    
    # Atmospheric alerts
    atm = payload.data.atmospheric_node.sensors
    
    if atm.wind_speed > 15:
        alerts.append(
            AlertRecord(
                hub_id=payload.hub_id,
                node_id=payload.data.atmospheric_node.node_id,
                message=f"💨 Warning: High wind speed detected ({atm.wind_speed:.1f} m/s) - Adjust irrigation schedule",
                level="warning",
                created_at=current_time,
            )
        )
    
    if atm.rain_intensity > 10:
        alerts.append(
            AlertRecord(
                hub_id=payload.hub_id,
                node_id=payload.data.atmospheric_node.node_id,
                message=f"🌧️ Info: Heavy rain detected ({atm.rain_intensity:.1f} mm/h) - Skip irrigation",
                level="info",
                created_at=current_time,
            )
        )
    
    if atm.air_humidity > 90:
        alerts.append(
            AlertRecord(
                hub_id=payload.hub_id,
                node_id=payload.data.atmospheric_node.node_id,
                message=f"💧 Info: High humidity ({atm.air_humidity:.1f}%) - Reduce irrigation frequency",
                level="info",
                created_at=current_time,
            )
        )
    
    return alerts


def store_alert(alert: AlertRecord) -> None:
    """Store alert in database"""
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
    """Serialize payload for database storage"""
    body = payload.dict()
    body["timestamp"] = payload.timestamp.replace(tzinfo=timezone.utc).isoformat()
    return body

# API Endpoints

@app.get("/", response_model=APIResponse)
async def root():
    """Root endpoint with API information"""
    return APIResponse(
        status="success",
        message="TerraSync IoT API v1.0.0 - Smart Farming Data Ingestion",
        data={
            "version": "1.0.0",
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
    api_key: str = Depends(verify_api_key)
) -> APIResponse:
    """
    Ingest telemetry data from IoT hub
    This is the main endpoint that IoT hubs call to send sensor data
    """
    try:
        # Store telemetry data
        record = serialize_payload(payload)
        db.add("telemetry", record)
        
        # Evaluate and store alerts
        alerts = evaluate_alerts(payload)
        for alert in alerts:
            store_alert(alert)
        
        return APIResponse(
            status="success",
            message=f"Data ingested successfully. {len(alerts)} alerts generated.",
            data={
                "hub_id": payload.hub_id,
                "received_at": datetime.now(timezone.utc).isoformat(),
                "alerts_triggered": [alert.message for alert in alerts],
                "alert_count": len(alerts)
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest data: {str(e)}"
        )

@app.get("/api/v1/data/latest", response_model=APIResponse)
async def get_latest_data(
    hub_id: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
) -> APIResponse:
    """Get latest telemetry data for a specific hub or all hubs"""
    try:
        records = db.get("telemetry")
        if hub_id:
            records = [item for item in records if item.get("hub_id") == hub_id]
        
        if not records:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No telemetry data available"
            )
        
        # Sort by timestamp and get latest
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
    limit: int = 50,
    api_key: str = Depends(verify_api_key)
) -> APIResponse:
    """Get historical telemetry data"""
    try:
        records = db.get("telemetry")
        if hub_id:
            records = [item for item in records if item.get("hub_id") == hub_id]
        
        # Sort by timestamp and limit results
        records.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
        limited_records = records[:limit]
        
        return APIResponse(
            status="success",
            message=f"Retrieved {len(limited_records)} historical records",
            data={
                "items": limited_records,
                "total_count": len(records),
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
    level: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
) -> APIResponse:
    """Get alerts for a specific hub or all hubs"""
    try:
        records = db.get("alerts")
        if hub_id:
            records = [item for item in records if item.get("hub_id") == hub_id]
        if level:
            records = [item for item in records if item.get("level") == level]
        
        # Sort by timestamp and limit results
        records.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        limited_records = records[:limit]
        
        return APIResponse(
            status="success",
            message=f"Retrieved {len(limited_records)} alerts",
            data={
                "items": limited_records,
                "total_count": len(records),
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
    hub_data: HubRegistration,
    api_key: str = Depends(verify_api_key)
) -> APIResponse:
    """Register a new IoT hub"""
    try:
        # Check if hub already exists
        existing_hubs = db.get("iot_hubs", {"hub_id": hub_data.hub_id})
        if existing_hubs:
            return APIResponse(
                status="warning",
                message="Hub already registered",
                data={"hub_id": hub_data.hub_id}
            )
        
        # Register new hub
        hub_record = {
            "hub_id": hub_data.hub_id,
            "user_email": hub_data.user_email,
            "location": hub_data.location,
            "description": hub_data.description,
            "field_id": hub_data.field_id,
            "status": "active",
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "last_seen": datetime.now(timezone.utc).isoformat()
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
    sensor_data: SensorRegistration,
    api_key: str = Depends(verify_api_key)
) -> APIResponse:
    """Register a new sensor node"""
    try:
        # Check if sensor already exists
        existing_sensors = db.get("sensors", {"node_id": sensor_data.node_id})
        if existing_sensors:
            return APIResponse(
                status="warning",
                message="Sensor already registered",
                data={"node_id": sensor_data.node_id}
            )
        
        # Register new sensor
        sensor_record = {
            "hub_id": sensor_data.hub_id,
            "node_id": sensor_data.node_id,
            "sensor_type": sensor_data.sensor_type,
            "location": sensor_data.location,
            "description": sensor_data.description,
            "status": "active",
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "last_seen": datetime.now(timezone.utc).isoformat()
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
    hub_id: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
) -> APIResponse:
    """Get hub status and connected sensors"""
    try:
        if hub_id:
            hubs = db.get("iot_hubs", {"hub_id": hub_id})
            sensors = db.get("sensors", {"hub_id": hub_id})
        else:
            hubs = db.get("iot_hubs")
            sensors = db.get("sensors")
        
        # Get latest telemetry for each hub
        telemetry = db.get("telemetry")
        hub_status = []
        
        for hub in hubs:
            hub_id = hub.get("hub_id")
            hub_sensors = [s for s in sensors if s.get("hub_id") == hub_id]
            hub_telemetry = [t for t in telemetry if t.get("hub_id") == hub_id]
            
            latest_telemetry = None
            if hub_telemetry:
                hub_telemetry.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                latest_telemetry = hub_telemetry[0]
            
            hub_status.append({
                "hub": hub,
                "sensors": hub_sensors,
                "sensor_count": len(hub_sensors),
                "latest_telemetry": latest_telemetry,
                "last_data_time": latest_telemetry.get("timestamp") if latest_telemetry else None
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
    """Health check endpoint"""
    return APIResponse(
        status="success",
        message="TerraSync IoT API is healthy",
        data={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": "connected"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
