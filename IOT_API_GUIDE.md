# 🌱 TerraSync IoT API - Hướng Dẫn Sử Dụng

## 📋 Tổng Quan

TerraSync IoT API là phần backend để nhận và xử lý dữ liệu từ các IoT hub trong hệ thống nông nghiệp thông minh. API này cung cấp các endpoint để:

- 📡 Nhận dữ liệu cảm biến từ IoT hub
- 🏠 Đăng ký hub và sensor mới  
- 🚨 Quản lý alerts và cảnh báo
- 📊 Truy xuất dữ liệu lịch sử và real-time

## 🚀 Cài Đặt và Chạy

### 1. Setup Environment

```bash
# Activate conda environment
conda activate ts

# Install dependencies
pip install -r requirements.txt
```

### 2. Chạy IoT API Server

```bash
# Start IoT API server
cd iotAPI
./run_api.sh
```

API sẽ chạy tại: `http://localhost:8000`

### 3. Chạy Streamlit App

```bash
# In another terminal, start Streamlit app
./run_app.sh
```

Streamlit app sẽ chạy tại: `http://localhost:8501`

## 📡 API Endpoints

### Authentication
Tất cả endpoints yêu cầu API key trong header:
```
Authorization: Bearer terrasync-iot-2024
```

### 1. Data Ingestion (Endpoint chính)
```http
POST /api/v1/data/ingest
```

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

### 2. Hub Registration
```http
POST /api/v1/hub/register
```

### 3. Sensor Registration  
```http
POST /api/v1/sensor/register
```

### 4. Get Latest Data
```http
GET /api/v1/data/latest?hub_id=hub-001
```

### 5. Get Data History
```http
GET /api/v1/data/history?hub_id=hub-001&limit=50
```

### 6. Get Alerts
```http
GET /api/v1/alerts?hub_id=hub-001&limit=50&level=critical
```

## 🧪 Testing

### Test IoT API
```bash
# Test IoT API endpoints
cd iotAPI
python test_api.py
```

### Test Integration
```bash
# Test full integration
python test_iot_integration.py
```

## 🔧 Cấu Hình IoT Hub

### 1. Đăng Ký Hub

Trong Streamlit app, vào **IoT Management** → **Hub Management**:

1. Nhập thông tin hub:
   - Hub Name: Tên hub
   - Location: Vị trí
   - IP Address: Địa chỉ IP
   - Coordinates: Tọa độ GPS
   - RF Channel: Kênh RF (1-10)

2. Click **Register Hub**
3. Lưu lại Hub ID được tạo

### 2. Đăng Ký Sensors

Sau khi có Hub ID, đăng ký các sensors:

- **Soil Sensors**: Cảm biến độ ẩm và nhiệt độ đất
- **Atmospheric Sensor**: Cảm biến thời tiết

### 3. Gửi Dữ Liệu

IoT hub gọi API endpoint `/api/v1/data/ingest` mỗi 10-15 phút với dữ liệu cảm biến.

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

## 🔗 Integration với Streamlit App

### 1. IoT Management Page
- **Hub Management**: Đăng ký và quản lý IoT hubs
- **Sensor Management**: Quản lý sensors
- **Real-time Data**: Xem dữ liệu thời gian thực
- **Alerts**: Xem và quản lý alerts
- **Settings**: Cấu hình IoT

### 2. Dashboard Integration
- Hiển thị dữ liệu IoT trên dashboard
- Alerts hiển thị trong real-time
- Tích hợp với irrigation scheduling

### 3. Database Integration
- Dữ liệu IoT được lưu trong `database.py`
- Alerts được lưu và hiển thị
- User-specific data filtering

## 🛠️ Troubleshooting

### 1. IoT API không chạy
```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill process if needed
kill -9 <PID>

# Restart API
cd iotAPI && ./run_api.sh
```

### 2. Connection Error
- Kiểm tra IoT API server đang chạy
- Kiểm tra firewall settings
- Verify API key trong requests

### 3. Database Error
- Kiểm tra quyền ghi file `terrasync_db.json`
- Restart cả IoT API và Streamlit app

### 4. Sensor Data không hiển thị
- Kiểm tra hub registration
- Verify sensor registration
- Check data format trong API calls

## 📝 Example Usage

### Python Client Example
```python
from iot_api_client import get_iot_client

# Get client
client = get_iot_client()

# Register hub
hub_data = {
    "hub_id": "my-hub-001",
    "user_email": "farmer@example.com",
    "location": {"lat": 20.450123, "lon": 106.325678},
    "description": "Main field hub"
}
client.register_hub(hub_data)

# Send telemetry data
telemetry_data = {
    "hub_id": "my-hub-001",
    "timestamp": "2024-01-15T10:30:00Z",
    "data": {
        "soil_nodes": [{
            "node_id": "soil-01",
            "sensors": {
                "soil_moisture": 35.2,
                "soil_temperature": 28.5
            }
        }],
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
client.send_telemetry_data(telemetry_data)

# Get latest data
latest_data = client.get_latest_data("my-hub-001")
print(latest_data)
```

### cURL Example
```bash
# Send telemetry data
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

## 🚀 Production Deployment

### Environment Variables
```bash
export API_HOST=0.0.0.0
export API_PORT=8000
export DATABASE_PATH=/path/to/db.json
export API_KEY_SECRET=your-secret-key
```

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "iotAPI.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 📞 Support

Nếu gặp vấn đề, hãy:

1. Kiểm tra logs trong terminal
2. Chạy test suite: `python test_iot_integration.py`
3. Xem API documentation: `http://localhost:8000/docs`
4. Kiểm tra database file permissions

---

**TerraSync IoT API** - Smart Farming Data Ingestion System 🌱
