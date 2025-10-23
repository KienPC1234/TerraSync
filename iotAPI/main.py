from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

from db import DatabaseManager


class SoilSensors(BaseModel):
    soil_moisture: float = Field(..., ge=0)
    soil_temperature: float


class SoilNode(BaseModel):
    node_id: str
    sensors: SoilSensors


class AtmosphericSensors(BaseModel):
    air_temperature: float
    air_humidity: float
    rain_intensity: float
    wind_speed: float
    light_intensity: float
    barometric_pressure: float


class AtmosphericNode(BaseModel):
    node_id: str
    sensors: AtmosphericSensors


class TelemetryData(BaseModel):
    soil_nodes: List[SoilNode]
    atmospheric_node: AtmosphericNode


class TelemetryPayload(BaseModel):
    hub_id: str
    timestamp: datetime
    location: Optional[Dict[str, float]]
    data: TelemetryData

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
    level: str
    created_at: datetime


db = DatabaseManager()

app = FastAPI(title="TerraSync IoT API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def evaluate_alerts(payload: TelemetryPayload) -> List[AlertRecord]:
    alerts: List[AlertRecord] = []
    for node in payload.data.soil_nodes:
        moisture = node.sensors.soil_moisture
        temperature = node.sensors.soil_temperature
        if moisture < 25:
            alerts.append(
                AlertRecord(
                    hub_id=payload.hub_id,
                    node_id=node.node_id,
                    message=f"Soil moisture at {node.node_id} is critically low ({moisture}%)",
                    level="critical",
                    created_at=datetime.now(timezone.utc),
                )
            )
        elif moisture > 80:
            alerts.append(
                AlertRecord(
                    hub_id=payload.hub_id,
                    node_id=node.node_id,
                    message=f"Soil moisture at {node.node_id} is above optimal ({moisture}%)",
                    level="warning",
                    created_at=datetime.now(timezone.utc),
                )
        if temperature > 35:
            alerts.append(
                AlertRecord(
                    hub_id=payload.hub_id,
                    node_id=node.node_id,
                    message=f"Soil temperature at {node.node_id} is high ({temperature}°C)",
                    level="warning",
                    created_at=datetime.now(timezone.utc),
                )
    atm = payload.data.atmospheric_node.sensors
    if atm.wind_speed > 12:
        alerts.append(
            AlertRecord(
                hub_id=payload.hub_id,
                node_id=payload.data.atmospheric_node.node_id,
                message=f"Wind speed is elevated ({atm.wind_speed} m/s)",
                level="info",
                created_at=datetime.now(timezone.utc),
            )
        )
    if atm.rain_intensity > 5:
        alerts.append(
            AlertRecord(
                hub_id=payload.hub_id,
                node_id=payload.data.atmospheric_node.node_id,
                message=f"Rain intensity reported at {atm.rain_intensity} mm/h",
                level="info",
                created_at=datetime.now(timezone.utc),
            )
        )
    return alerts


def store_alert(alert: AlertRecord) -> None:
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
    body = payload.dict()
    body["timestamp"] = payload.timestamp.replace(tzinfo=timezone.utc).isoformat()
    return body


@app.post("/api/v1/data/ingest")
async def ingest(payload: TelemetryPayload) -> Dict[str, Any]:
    record = serialize_payload(payload)
    db.add("telemetry", record)
    alerts = evaluate_alerts(payload)
    for alert in alerts:
        store_alert(alert)
    return {
        "status": "success",
        "hub_id": payload.hub_id,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "alerts_triggered": [alert.message for alert in alerts],
    }


@app.get("/api/v1/data/latest")
async def latest(hub_id: Optional[str] = None) -> Dict[str, Any]:
    records = db.get("telemetry")
    if hub_id:
        records = [item for item in records if item.get("hub_id") == hub_id]
    if not records:
        raise HTTPException(status_code=404, detail="No telemetry data available")
    records.sort(key=lambda item: item.get("timestamp", ""))
    return records[-1]


@app.get("/api/v1/data/history")
async def history(hub_id: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    records = db.get("telemetry")
    if hub_id:
        records = [item for item in records if item.get("hub_id") == hub_id]
    records.sort(key=lambda item: item.get("timestamp", ""))
    return {"items": records[-limit:]}


@app.get("/api/v1/alerts")
async def alerts(hub_id: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    records = db.get("alerts")
    if hub_id:
        records = [item for item in records if item.get("hub_id") == hub_id]
    records.sort(key=lambda item: item.get("created_at", ""))
    return {"items": records[-limit:]}
