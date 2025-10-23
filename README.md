# 🌱 TerraSync IoT - Hệ Thống Nông Nghiệp Thông Minh

## 📋 Tổng Quan Dự Án

TerraSync IoT là hệ thống nông nghiệp thông minh tích hợp AI, IoT và dữ liệu vệ tinh để tối ưu hóa quản lý nước tưới tiêu và sức khỏe cây trồng. Hệ thống giúp nông dân giảm lãng phí nước lên đến 60%, dự đoán rủi ro thời tiết sớm và chẩn đoán bệnh cây trồng qua hình ảnh.

## 🚀 Tính Năng Chính

### 🤖 AI & Computer Vision
- **AI YOLO Field Detection**: Tự động khoanh vùng ruộng từ ảnh vệ tinh/thực tế
- **Plant Disease Diagnosis**: Chẩn đoán bệnh cây trồng từ ảnh lá
- **Satellite Image Processing**: Xử lý ảnh vệ tinh với AI upscaling

### 📡 IoT Management
- **Hub Management**: Quản lý IoT hub chính (Raspberry Pi 4)
- **Sensor Monitoring**: Theo dõi cảm biến thời gian thực
- **RF 433MHz Communication**: Giao tiếp khoảng cách xa ~1km
- **Real-time Data**: Dữ liệu cảm biến độ ẩm, nhiệt độ, gió, mưa

### 🛰️ Satellite & Weather
- **Satellite View**: Xem ruộng qua ảnh vệ tinh
- **NDVI Analysis**: Phân tích chỉ số thực vật
- **Weather Forecast**: Dự báo thời tiết 7 ngày
- **Risk Assessment**: Đánh giá rủi ro thời tiết

### 💬 CropNet AI Assistant
- **Smart Chatbot**: Trợ lý AI dựa trên Gemini
- **Contextual Advice**: Lời khuyên dựa trên dữ liệu cảm biến
- **Multi-language Support**: Hỗ trợ đa ngôn ngữ

## 🛠️ Cài Đặt & Chạy

### 1. Cài Đặt Conda Environment

```bash
# Chạy script setup
./setup_conda.sh

# Hoặc tạo thủ công
conda env create -f environment.yml
conda activate ts
```

### 2. Cấu Hình API Keys

Tạo file `.streamlit/secrets.toml`:

```toml
[gemini]
api_key = "YOUR_GEMINI_API_KEY"

[auth]
redirect_uri = "http://localhost:8502/oauth2callback"
cookie_secret = "YOUR_COOKIE_SECRET"
client_id = "YOUR_GOOGLE_CLIENT_ID"
client_secret = "YOUR_GOOGLE_CLIENT_SECRET"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

### 3. Chạy Ứng Dụng

```bash
# Kích hoạt environment
conda activate ts

# Chạy Streamlit app
streamlit run streamlit_app.py
```

## 📁 Cấu Trúc Dự Án

```
TerraSync/
├── streamlit_app.py          # Main application
├── database.py               # Database manager
├── api_placeholders.py       # API placeholders
├── utils.py                  # Utility functions
├── environment.yml           # Conda environment
├── setup_conda.sh           # Setup script
├── pages/                   # Application pages
│   ├── dashboard.py         # Main dashboard
│   ├── chat.py              # CropNet AI chat
│   ├── my_fields.py         # Field management
│   ├── my_schedule.py       # Irrigation schedule
│   ├── iot_management.py    # IoT device management
│   ├── ai_field_detection.py # AI field detection
│   ├── satellite_view.py    # Satellite view
│   ├── settings.py          # Settings
│   ├── help_center.py       # Help center
│   └── login.py             # Authentication
├── iotAPI/                  # IoT API server
│   └── main.py              # FastAPI server
└── .streamlit/              # Streamlit config
    ├── config.toml          # Streamlit config
    └── secrets.toml         # API keys
```

## 🔧 Công Nghệ Sử Dụng

### Backend
- **Python 3.11**: Ngôn ngữ chính
- **Streamlit**: Web framework
- **FastAPI**: IoT API server
- **SQLite/JSON**: Database

### AI & ML
- **Google Gemini API**: LLM chatbot
- **YOLO**: Object detection
- **OpenCV**: Image processing
- **PyTorch**: Deep learning

### IoT & Hardware
- **Raspberry Pi 4**: IoT hub chính
- **Arduino Pro Mini**: Node cảm biến
- **RF 433MHz**: Giao tiếp không dây
- **Various Sensors**: Độ ẩm, nhiệt độ, gió, mưa

### APIs & Services
- **OpenET (NASA)**: Evapotranspiration data
- **Open-Meteo**: Weather data
- **Google OAuth**: Authentication
- **Leaflet/OpenStreetMap**: Maps

## 📊 Database Schema

### Users Table
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "User Name",
  "picture": "profile_pic_url",
  "first_login": "2025-01-15T10:00:00Z",
  "last_login": "2025-01-15T10:00:00Z",
  "is_active": true
}
```

### Fields Table
```json
{
  "id": "uuid",
  "user_email": "user@example.com",
  "name": "Field Name",
  "crop": "Rice",
  "area": 2.5,
  "polygon": [[lat, lon], ...],
  "center": [lat, lon],
  "created_by": "AI Detection"
}
```

### IoT Hubs Table
```json
{
  "id": "uuid",
  "hub_id": "hub_123456",
  "user_email": "user@example.com",
  "name": "Main Farm Hub",
  "location": "Field A",
  "ip_address": "192.168.1.100",
  "coordinates": {"lat": 20.45, "lon": 106.32},
  "rf_channel": 1
}
```

## 🌐 API Endpoints

### IoT Data Ingestion
```
POST /api/v1/data/ingest
Content-Type: application/json

{
  "hub_id": "c72b56e1-1b9a-46a8-a7b8-0a6ef27b3b72",
  "timestamp": "2025-01-15T10:00:00Z",
  "location": {"lat": 20.45, "lon": 106.32},
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
        "wind_speed": 2.1
      }
    }
  }
}
```

## 🚀 Chạy IoT API Server

```bash
# Chạy FastAPI server
cd iotAPI
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 📱 Sử Dụng Ứng Dụng

### 1. Đăng Nhập
- Sử dụng tài khoản Google để đăng nhập
- Hệ thống tự động lưu thông tin user vào database

### 2. Quản Lý Fields
- Thêm ruộng mới thủ công hoặc sử dụng AI detection
- Upload ảnh vệ tinh để AI tự động khoanh vùng
- Xem thông tin chi tiết và trạng thái ruộng

### 3. IoT Management
- Đăng ký IoT hub mới
- Quản lý cảm biến và theo dõi trạng thái
- Xem dữ liệu thời gian thực

### 4. AI Detection
- Upload ảnh để AI chẩn đoán bệnh cây
- Tự động khoanh vùng ruộng từ ảnh
- Lưu kết quả phân tích

### 5. Satellite View
- Xem ruộng qua ảnh vệ tinh
- Phân tích NDVI và thực vật
- Dự báo thời tiết và đánh giá rủi ro

### 6. CropNet AI
- Chat với AI assistant
- Nhận lời khuyên dựa trên dữ liệu cảm biến
- Hỗ trợ đa ngôn ngữ

## 🔧 Troubleshooting

### Lỗi thường gặp:

1. **Missing API Keys**
   - Kiểm tra file `.streamlit/secrets.toml`
   - Đảm bảo có đầy đủ API keys

2. **Database Errors**
   - Xóa file `terrasync_db.json` để reset database
   - Kiểm tra quyền ghi file

3. **Import Errors**
   - Chạy `conda activate ts`
   - Cài đặt lại dependencies: `pip install -r requirements.txt`

4. **IoT Connection Issues**
   - Kiểm tra IoT API server đang chạy
   - Verify hub ID và network connection

## 📈 Roadmap

### Phase 1 (Current)
- ✅ Basic web interface
- ✅ User authentication
- ✅ Database management
- ✅ AI placeholders
- ✅ IoT management UI

### Phase 2 (Next)
- 🔄 Real YOLO model integration
- 🔄 Actual IoT hardware integration
- 🔄 Real-time data processing
- 🔄 Mobile app development

### Phase 3 (Future)
- 📅 Advanced ML models
- 📅 Multi-farm management
- 📅 Predictive analytics
- 📅 Integration with external APIs

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

- Email: support@terrasync.io
- Documentation: [docs.terrasync.io](https://docs.terrasync.io)
- Issues: [GitHub Issues](https://github.com/terrasync/issues)

---

**TerraSync IoT** - Nông nghiệp thông minh, kết nối toàn diện từ đất đai đến đám mây 🌱
