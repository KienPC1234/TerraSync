# TerraSync IoT API

## 🌱 Overview

TerraSync IoT API là phần backend API để nhận và xử lý dữ liệu từ các IoT hub trong hệ thống nông nghiệp thông minh TerraSync. API này cung cấp các endpoint để:

- Nhận dữ liệu cảm biến từ IoT hub
- Đăng ký hub và sensor mới
- Quản lý alerts và cảnh báo
- Truy xuất dữ liệu lịch sử và real-time

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Activate conda environment
conda activate ts

# Install dependencies
pip install -r requirements.txt
```

### 2. Run API Server

```bash
# Start the API server
./run_api.sh
```

API sẽ chạy tại: `http://localhost:8000`

### 3. API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📡 API Endpoints

### Authentication
Tất cả endpoints yêu cầu API key trong header:
```
Authorization: Bearer terrasync-iot-2024
```

### Core Endpoints

#### 1. Data Ingestion
```http
POST /api/v1/data/ingest
```
Endpoint chính để IoT hub gửi dữ liệu cảm biến.

**Request Body:**
```json
{
  "hub_id": "hub-001",
  "timestamp": "2024-01-15T10:30:00Z",
  "location": {
    "lat": 20.450123,
    "lon": 106.325678
  },
  "data": {
    "soil_nodes": [
      {
        "node_id": "soil-01",
        "sensors": {
          "soil_moisture": 32.5,
          "soil_temperature": 28.1
        }
      }
    ],
    "atmospheric_node": {
      "node_id": "atm-01",
      "sensors": {
        "air_temperature": 31.3,
        "air_humidity": 68.4,
        "rain_intensity": 0,
        "wind_speed": 2.1,
        "light_intensity": 820,
        "barometric_pressure": 1008.5
      }
    }
  }
}
```

#### 2. Get Latest Data
```http
GET /api/v1/data/latest?hub_id=hub-001
```

#### 3. Get Data History
```http
GET /api/v1/data/history?hub_id=hub-001&limit=50
```

#### 4. Get Alerts
```http
GET /api/v1/alerts?hub_id=hub-001&limit=50&level=critical
```

### Management Endpoints

#### 5. Register Hub
```http
POST /api/v1/hub/register
```
```json
{
  "hub_id": "hub-001",
  "user_email": "farmer@example.com",
  "location": {
    "lat": 20.450123,
    "lon": 106.325678
  },
  "description": "Main field hub",
  "field_id": "field-001"
}
```

#### 6. Register Sensor
```http
POST /api/v1/sensor/register
```
```json
{
  "hub_id": "hub-001",
  "node_id": "soil-01",
  "sensor_type": "soil",
  "location": {
    "lat": 20.450123,
    "lon": 106.325678
  },
  "description": "Soil sensor node 1"
}
```

#### 7. Get Hub Status
```http
GET /api/v1/hub/status?hub_id=hub-001
```

## 🧪 Testing

### Run Test Suite
```bash
# Make sure API server is running first
./run_api.sh

# In another terminal, run tests
python test_api.py
```

### Manual Testing with curl

```bash
# Test health check
curl http://localhost:8000/health

# Test data ingestion
curl -X POST http://localhost:8000/api/v1/data/ingest \
  -H "Authorization: Bearer terrasync-iot-2024" \
  -H "Content-Type: application/json" \
  -d '{
    "hub_id": "test-hub",
    "timestamp": "2024-01-15T10:30:00Z",
    "data": {
      "soil_nodes": [{
        "node_id": "soil-01",
        "sensors": {
          "soil_moisture": 25.0,
          "soil_temperature": 28.0
        }
      }],
      "atmospheric_node": {
        "node_id": "atm-01",
        "sensors": {
          "air_temperature": 30.0,
          "air_humidity": 70.0,
          "rain_intensity": 0,
          "wind_speed": 2.0,
          "light_intensity": 800,
          "barometric_pressure": 1000.0
        }
      }
    }
  }'
```

## 🚨 Alert System

API tự động tạo alerts dựa trên dữ liệu cảm biến:

### Soil Moisture Alerts
- **Critical** (< 20%): Cần tưới nước ngay lập tức
- **Warning** (20-30%): Cân nhắc tưới nước
- **Info** (> 85%): Giảm tần suất tưới

### Soil Temperature Alerts
- **Warning** (> 40°C): Kiểm tra stress nhiệt
- **Warning** (< 5°C): Kiểm tra thiệt hại do sương giá

### Atmospheric Alerts
- **Warning** (Wind > 15 m/s): Điều chỉnh lịch tưới
- **Info** (Rain > 10 mm/h): Bỏ qua tưới nước
- **Info** (Humidity > 90%): Giảm tần suất tưới

## 🔧 Configuration

### API Keys
Mặc định có 2 API keys:
- `terrasync-iot-2024`: Key chính
- `hub-master-key`: Key cho hub

### Database
API sử dụng cùng database với Streamlit app (`database.py`).

## 📊 Data Schema

### Telemetry Data Structure
```json
{
  "hub_id": "string",
  "timestamp": "ISO 8601 datetime",
  "location": {
    "lat": "float",
    "lon": "float"
  },
  "data": {
    "soil_nodes": [
      {
        "node_id": "string",
        "sensors": {
          "soil_moisture": "float (0-100%)",
          "soil_temperature": "float (°C)"
        }
      }
    ],
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

## 🔗 Integration with Streamlit App

IoT API được tích hợp với Streamlit app thông qua:

1. **Shared Database**: Cùng sử dụng `database.py`
2. **Real-time Data**: Streamlit app có thể gọi API để lấy dữ liệu mới nhất
3. **Alert Integration**: Alerts từ API hiển thị trong Streamlit dashboard

## 🛠️ Development

### Project Structure
```
iotAPI/
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
├── run_api.sh          # Server startup script
├── test_api.py         # Test suite
└── README.md           # This file
```

### Adding New Endpoints
1. Define Pydantic models in `main.py`
2. Create endpoint function with proper error handling
3. Add authentication with `@Depends(verify_api_key)`
4. Update tests in `test_api.py`

## 🚀 Production Deployment

### Environment Variables
```bash
export API_HOST=0.0.0.0
export API_PORT=8000
export DATABASE_PATH=/path/to/db.json
```

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 📝 License

TerraSync IoT API - Smart Farming Data Ingestion System
