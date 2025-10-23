# 🌱 TerraSync IoT API - Tóm Tắt Hoàn Thành

## ✅ Đã Hoàn Thành

### 1. **IoT API Server** (`iotAPI/main.py`)
- ✅ FastAPI server với đầy đủ endpoints
- ✅ Authentication với API keys
- ✅ Data validation với Pydantic models
- ✅ Automatic alert generation
- ✅ Database integration với `database.py`
- ✅ CORS middleware cho cross-origin requests
- ✅ Comprehensive error handling

### 2. **API Endpoints**
- ✅ `POST /api/v1/data/ingest` - Nhận dữ liệu từ IoT hub
- ✅ `GET /api/v1/data/latest` - Lấy dữ liệu mới nhất
- ✅ `GET /api/v1/data/history` - Lấy lịch sử dữ liệu
- ✅ `GET /api/v1/alerts` - Lấy alerts
- ✅ `POST /api/v1/hub/register` - Đăng ký hub
- ✅ `POST /api/v1/sensor/register` - Đăng ký sensor
- ✅ `GET /api/v1/hub/status` - Trạng thái hub
- ✅ `GET /health` - Health check

### 3. **IoT API Client** (`iot_api_client.py`)
- ✅ Python client để giao tiếp với IoT API
- ✅ Cached client instance với Streamlit
- ✅ Error handling và timeout
- ✅ Helper functions cho tạo sample data
- ✅ Integration với Streamlit app

### 4. **Streamlit Integration**
- ✅ Cập nhật `pages/iot_management.py` để tích hợp IoT API
- ✅ Thêm tab "Alerts" để hiển thị alerts từ IoT API
- ✅ Hub registration với IoT API
- ✅ Real-time data display
- ✅ Connection testing

### 5. **Testing & Documentation**
- ✅ `iotAPI/test_api.py` - Test suite cho IoT API
- ✅ `test_iot_integration.py` - Integration test
- ✅ `iotAPI/README.md` - Documentation cho IoT API
- ✅ `IOT_API_GUIDE.md` - Hướng dẫn sử dụng chi tiết
- ✅ `iotAPI/run_api.sh` - Script chạy IoT API

### 6. **Dependencies & Setup**
- ✅ Cập nhật `requirements.txt` với IoT API dependencies
- ✅ `iotAPI/requirements.txt` - Dependencies riêng cho IoT API
- ✅ Environment setup scripts

## 🚀 Cách Sử Dụng

### 1. **Chạy IoT API Server**
```bash
# Terminal 1: Start IoT API
cd iotAPI
./run_api.sh
```

### 2. **Chạy Streamlit App**
```bash
# Terminal 2: Start Streamlit
./run_app.sh
```

### 3. **Test Integration**
```bash
# Test IoT API
cd iotAPI && python test_api.py

# Test full integration
python test_iot_integration.py
```

## 📡 Data Flow

```
IoT Hub (Raspberry Pi) 
    ↓ (RF 433MHz)
Sensor Nodes (Arduino)
    ↓ (HTTP POST)
IoT API Server (FastAPI)
    ↓ (Database)
Streamlit App
    ↓ (Display)
User Interface
```

## 🔧 Key Features

### **Automatic Alert System**
- Soil moisture < 20% → Critical alert
- Soil moisture 20-30% → Warning alert
- Soil temperature > 40°C → Warning alert
- Wind speed > 15 m/s → Warning alert
- Rain intensity > 10 mm/h → Info alert

### **Real-time Data Processing**
- Nhận dữ liệu từ IoT hub mỗi 10-15 phút
- Tự động lưu vào database
- Tạo alerts dựa trên ngưỡng
- Hiển thị real-time trong Streamlit

### **Hub & Sensor Management**
- Đăng ký hub với unique ID
- Quản lý sensors (soil, atmospheric)
- Theo dõi trạng thái kết nối
- Battery level monitoring

## 🎯 API Usage Examples

### **Register Hub**
```python
from iot_api_client import get_iot_client

client = get_iot_client()
hub_data = {
    "hub_id": "hub-001",
    "user_email": "farmer@example.com",
    "location": {"lat": 20.45, "lon": 106.32},
    "description": "Main field hub"
}
client.register_hub(hub_data)
```

### **Send Telemetry Data**
```python
telemetry_data = {
    "hub_id": "hub-001",
    "timestamp": "2024-01-15T10:30:00Z",
    "data": {
        "soil_nodes": [{
            "node_id": "soil-01",
            "sensors": {
                "soil_moisture": 25.0,  # Will trigger alert
                "soil_temperature": 28.0
            }
        }],
        "atmospheric_node": {
            "node_id": "atm-01",
            "sensors": {
                "air_temperature": 30.0,
                "air_humidity": 70.0,
                "wind_speed": 2.0
            }
        }
    }
}
client.send_telemetry_data(telemetry_data)
```

### **Get Alerts**
```python
alerts = client.get_alerts("hub-001", level="critical")
for alert in alerts:
    print(f"🚨 {alert['message']}")
```

## 🔗 Integration Points

### **Streamlit App Integration**
- `pages/iot_management.py` - IoT device management
- `iot_api_client.py` - API client wrapper
- `database.py` - Shared database
- Real-time alerts display
- Hub registration UI

### **Database Integration**
- Shared `terrasync_db.json` file
- Tables: `iot_hubs`, `sensors`, `telemetry`, `alerts`
- User-specific data filtering
- Automatic data persistence

## 🚨 Alert System

### **Alert Levels**
- **Critical**: Cần hành động ngay lập tức
- **Warning**: Cần chú ý và theo dõi
- **Info**: Thông tin bổ sung

### **Alert Types**
- Soil moisture alerts
- Soil temperature alerts
- Wind speed alerts
- Rain intensity alerts
- Humidity alerts

## 📊 Data Schema

### **Telemetry Data**
```json
{
  "hub_id": "string",
  "timestamp": "ISO 8601",
  "location": {"lat": float, "lon": float},
  "data": {
    "soil_nodes": [{
      "node_id": "string",
      "sensors": {
        "soil_moisture": "float (0-100%)",
        "soil_temperature": "float (°C)"
      }
    }],
    "atmospheric_node": {
      "node_id": "string",
      "sensors": {
        "air_temperature": "float (°C)",
        "air_humidity": "float (0-100%)",
        "rain_intensity": "float (mm/h)",
        "wind_speed": "float (m/s)",
        "light_intensity": "float (Lux)",
        "barometric_pressure": "float (hPa)"
      }
    }
  }
}
```

## 🎉 Kết Quả

**TerraSync IoT API đã được hoàn thiện với:**

✅ **FastAPI server** đầy đủ chức năng  
✅ **Real-time data ingestion** từ IoT hub  
✅ **Automatic alert system** thông minh  
✅ **Streamlit integration** hoàn chỉnh  
✅ **Comprehensive testing** suite  
✅ **Detailed documentation** và hướng dẫn  
✅ **Production-ready** code với error handling  

**Hệ thống IoT API giờ đây sẵn sàng để:**
- Nhận dữ liệu từ IoT hub thực tế
- Xử lý và lưu trữ dữ liệu cảm biến
- Tạo alerts tự động
- Hiển thị real-time data trong Streamlit app
- Quản lý hub và sensors
- Mở rộng cho production deployment

🌱 **TerraSync IoT - Nông nghiệp thông minh, kết nối toàn diện!**
