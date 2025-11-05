Tóm Tắt Dự Án TerraSync IoT: Hệ Thống Nông Nghiệp Thông Minh Tích Hợp IoT Và AI Cho Quản Lý Nước, Ruộng Bền Vững
Giới Thiệu Dự Án Và Ý Tưởng Cốt Lõi
TerraSync là phiên bản nâng cấp của giải pháp tối ưu hóa quản lý nước tưới tiêu và sức khỏe cây trồng dành cho nông dân. Với ý tưởng cốt lõi là "Nông nghiệp thông minh, kết nối toàn diện từ đất đai đến đám mây", dự án tích hợp AI tiên tiến, IoT thực tế và dữ liệu vệ tinh để tạo hệ sinh thái tự động, giúp nông dân giảm lãng phí nước lên đến 60% (theo WWF), dự đoán rủi ro thời tiết sớm và chẩn đoán bệnh cây trồng qua hình ảnh.
Sử dụng dữ liệu evapotranspiration (ET) từ OpenET của NASA, kết hợp Gemini API cho xử lý ngôn ngữ tự nhiên, TerraSync  cho phép nông dân vẽ bản đồ ruộng, nhập dữ liệu cây trồng và nhận lịch tưới 7 ngày cá nhân hóa. Ý tưởng mới tập trung vào tính tự động hóa: AI tự khoanh vùng ruộng qua mô hình CNN YOLO, xử lý ảnh upload để phát hiện bệnh lá, và cụm IoT với Raspberry Pi 4 hoặc máy tính làm trung tâm xử lý cho từng ruộng, kết nối cảm biến thời gian thực qua công nghệ RF 433MHz để đảm bảo khoảng cách xa và tiết kiệm năng lượng.
CropNet AI 🌱 được nâng cấp thành LLM thông minh hơn (dựa trên Gemini), hỗ trợ đọc dữ liệu cảm biến, đưa lời khuyên cá nhân hóa (như "Đất ruộng A quá khô, nên tưới thêm 20% vào tối nay") và trò chuyện đa ngôn ngữ cho nông dân. Dự án thúc đẩy nông nghiệp bền vững, tăng năng suất và giảm rủi ro, đặc biệt ở khu vực dễ chịu ảnh hưởng thời tiết cực đoan.
Chức Năng Chính Của TerraSync IoT
TerraSync là ứng dụng web (dựa trên Streamlit) hỗ trợ tối ưu hóa lịch tưới tiêu, giám sát IoT và chẩn đoán AI. Nông dân có thể:
Tự động khoanh vùng ruộng qua AI CNN YOLO: Upload ảnh vệ tinh hoặc ảnh thực tế, AI tự detect và gợi ý vùng ruộng để chọn, giảm thời gian vẽ thủ công.
Upload ảnh cây trồng: AI xử lý hình ảnh (sử dụng YOLO cho object detection) để dự đoán bệnh (như nấm mốc, sâu bệnh), khoanh vùng tổn thương lá và gợi ý điều trị.
Quản lý IoT: Kết nối hub chính (Raspberry Pi 4 hoặc máy tính) cho từng ruộng, theo dõi cảm biến thời gian thực (độ ẩm đất, gió, mưa, ánh sáng) qua trang quản lý thiết bị, sử dụng giao tiếp RF 433MHz để hỗ trợ khoảng cách lên đến 1km.
Dự đoán khí hậu: Model AI (dựa trên dữ liệu vệ tinh và Open-Meteo) cảnh báo sớm bão, hạn hán; tích hợp push notification (qua web/mobile) cho cảnh báo tự động như "Quên tưới ruộng B – đất khô 80%".
CropNet AI: Đọc dữ liệu cảm biến, đưa lời khuyên (ví dụ: "Dựa trên gió mạnh hôm nay, giảm tưới 15% để tránh bay hơi"), hỗ trợ xem ruộng qua ảnh vệ tinh (xử lý mây che bằng AI upscaling).
Giao diện responsive, hỗ trợ mobile để nông dân theo dõi mọi lúc.
Cách Hoạt Động Của TerraSync IoT
Ứng dụng trình bày dữ liệu hành động hóa, dễ sử dụng trên web/mobile.
Trang Dashboard Chính: Thời gian thực về trang trại, bao gồm bản đồ tương tác (Leaflet/OpenStreetMap) với hydrat hóa ruộng ("Hydrated"/"Dehydrated"). Tích hợp dữ liệu IoT: Hiển thị cảm biến (độ ẩm, gió, mưa, ánh sáng,...) từ hub chính. AI tự cảnh báo vấn đề (quên tưới, đất quá khô,...) qua push message.
Trang "My Fields": Tổng quan hydrat hóa, nước sử dụng hàng ngày, thời gian tưới. Theo dõi "Hydration Jobs" và thiết bị IoT. Thêm chức năng upload ảnh cây để AI chẩn đoán bệnh, khoanh vùng tổn thương.
Thêm Ruộng Mới: Nhập tọa độ/crop type/giai đoạn phát triển/hiệu suất tưới. AI YOLO tự khoanh vùng ruộng từ ảnh upload. Kết nối IoT: Vào mạng LAN hub để lấy ID, nhập ID trên web để check và đăng ký cảm biến (hub tự call API máy chủ mỗi 15 phút gửi danh sách cảm biến). Có thể đổi ID dễ dàng trong quản lý, tự thông báo khi có cảm biến bị hỏng, lỗi qua thông báo, chỉ việc thay cảm biến ở vị trí cũ.
Lịch Tưới Và Dự Đoán: Tính toán như trước (Shoelace cho diện tích, công thức (cropCoefficient × ET - precipitation) × area), nhưng tích hợp dữ liệu cảm biến IoT thời gian thực. Model dự đoán khí hậu (từ dữ liệu vệ tinh/khí tượng mở) cảnh báo sớm, gợi ý điều chỉnh lịch.
Quản Lý Thiết Bị IoT: Trang riêng xem trạng thái hub/cảm biến (kết nối, hỏng, thiếu thiết bị). Cảnh báo tự động nếu mất kết nối hoặc vấn đề (push message). Hub chính (Raspberry Pi 4 hoặc máy tính với cổng USB) hỗ trợ module USB riêng để cấp điện cho ăng ten RF 433MHz chính 17dBi, đảm bảo khoảng cách ~1km. Node con (cảm biến) sử dụng pin 1100mAh hỗ trợ sạc điện, tối đa dùng được 1 tháng trước khi tắt, với ăng ten 5dBi C1101 và chip MCU Arduino Pro Mini 3.3V điều khiển. Cơ chế thông minh: Thay vì node con liên tục phát tín hiệu, khi đăng ký thiết bị, node chính sẽ tạo ID cho node con và lưu vào EEPROM. Node chính chỉ cần mỗi 10 phút gọi từng node con một theo thứ tự (tuần tự từng node nhỏ), chờ node con trả lại tín hiệu cảm biến. Node con hoạt động ở chế độ ngủ tiết kiệm năng lượng, nghe ngắt quãng: Phần lớn ngủ, mỗi 5 giây sẽ nghe 1 lần trong vòng 500ms; khi nhận được lệnh gọi từ node chính, sẽ phát ra tín hiệu cảm biến, chờ node chính phát sóng OK rồi trở về ngủ chờ lệnh gọi tiếp theo. Tất cả các thiết bị đều có ID riêng và thêm cơ chế random (thời gian chờ ngẫu nhiên) để tránh xung đột sóng nếu nhiều ruộng gần nhau có nhiều node chính hoạt động đồng thời.
Xem Ruộng Qua Vệ Tinh: Tích hợp ảnh vệ tinh (OpenET), AI xử lý mây che để hiển thị rõ ràng.
Mục Tiêu Của Dự Án
Xây dựng hệ thống toàn diện giúp nông dân tối ưu tưới tiêu, chẩn đoán bệnh cây, dự đoán rủi ro thời tiết và giám sát IoT tự động. Giảm lãng phí nước, tăng năng suất 20-30%, thúc đẩy nông nghiệp 4.0. CropNet AI (Gemini-based) làm "người bạn đồng hành", đọc cảm biến và đưa lời khuyên thông minh.
Công Nghệ Sử Dụng (Cập Nhật)
Công Cụ Phát Triển: GitHub, Visual Studio Code.
Ngôn Ngữ: Python (chính), HTML/CSS, ThreeJS cho mô phỏng ruộng thiết bị IoT.
Framework: Streamlit (cho web nhanh, tích hợp AI dễ dàng).
Hạ Tầng: VPS máy chủ với 20 lõi CPU, 64GB RAM; Raspberry Pi 4 hoặc máy tính làm hub chính cho IoT.
API Và Model: Gemini API (LLM nâng cấp), OpenET (ET), Open-Meteo (thời tiết), Leaflet/OpenStreetMap (bản đồ), Gemini, CNN YOLO (object detection cho khoanh vùng/bệnh lá); Model dự đoán khí hậu (dựa trên PyTorch/Scikit-learn từ dữ liệu quá khứ).
IoT: Hub chính (Raspberry Pi 4 hoặc máy tính với cổng USB) kết nối module USB riêng cấp điện cho ăng ten RF 433MHz chính 17dBi (C1101); Node con sử dụng chip MCU Arduino Pro Mini 3.3V điều khiển, ăng ten 5dBi C1101, pin 1100mAh hỗ trợ sạc (cảm biến kháng nước: độ ẩm, gió, mưa, ánh sáng); Push notification qua Firebase. Cơ chế giao tiếp RF 433MHz với ID riêng, gọi tuần tự và random tránh xung đột.
Kế Hoạch Tương Lai
Tích hợp thêm dữ liệu vệ tinh (Sentinel/NOAA) cho dự đoán chính xác hơn.
Fine-tune YOLO/Gemini cho nông nghiệp Việt Nam (bệnh cây địa phương).
Xây dựng database đám mây (Firebase) lưu trữ dữ liệu IoT lâu dài.
Mở rộng IoT: Hỗ trợ camera cảm biến cho theo dõi sâu bệnh thời gian thực.
Phát triển app mobile native với AR xem ruộng ảo.
Thử nghiệm thực địa: Triển khai hub IoT ở 5 ruộng mẫu để kiểm tra độ bền. TerraSync IoT biến ý tưởng thành hiện thực: Một hệ thống kết nối AI-IoT-vệ tinh, giúp nông dân "nói chuyện" với đất đai của mình.
🌍 TerraSync IoT Data Schema v1
1. Metadata chung
{
  "hub_id": "UUID",               // Mã định danh duy nhất cho hub (được nhập khi đăng ký)
  "timestamp": "2025-10-22T20:15:00Z",  // ISO 8601 - thời gian ghi nhận dữ liệu
  "location": {                   // Tùy chọn, có thể bỏ trống nếu hub cố định
    "lat": 20.450123,
    "lon": 106.325678
  },
  "data": {                       // Dữ liệu tổng hợp từ các nhóm node
    ...
  }
}


2. Dữ liệu cảm biến
{
  "data": {
    "soil_nodes": [
      {
        "node_id": "soil-01",              // Mã node trong vườn
        "sensors": {
          "soil_moisture": 32.5,           // % độ ẩm đất
          "soil_temperature": 28.1          // °C nhiệt độ đất
        }
      },
      {
        "node_id": "soil-02",
        "sensors": {
          "soil_moisture": 45.2,
          "soil_temperature": 26.9
        }
      }
    ],
    "atmospheric_node": {
      "node_id": "atm-01",
      "sensors": {
        "air_temperature": 31.3,          // °C
        "air_humidity": 68.4,             // %
        "rain_intensity": 0,              // mm/h hoặc 1/0 nếu chỉ có cảm biến mưa
        "wind_speed": 2.1,                // m/s
        "light_intensity": 820,           // Lux
        "barometric_pressure": 1008.5     // hPa
      }
    }
  }
}


3. Ví dụ dữ liệu thực tế gửi lên server
{
  "hub_id": "c72b56e1-1b9a-46a8-a7b8-0a6ef27b3b72",
  "timestamp": "2025-10-22T13:42:00Z",
  "location": { "lat": 20.4512, "lon": 106.3312 },
  "data": {
    "soil_nodes": [
      {
        "node_id": "soil-01",
        "sensors": { "soil_moisture": 31.4, "soil_temperature": 27.8 }
      },
      {
        "node_id": "soil-02",
        "sensors": { "soil_moisture": 40.1, "soil_temperature": 26.2 }
      }
    ],
    "atmospheric_node": {
      "node_id": "atm-01",
      "sensors": {
        "air_temperature": 30.7,
        "air_humidity": 70.2,
        "rain_intensity": 0,
        "wind_speed": 1.8,
        "light_intensity": 950,
        "barometric_pressure": 1007.6
      }
    }
  }
}


4. API Endpoint Gợi Ý
POST /api/v1/data/ingest
Content-Type: application/json
Body: (the schema above)

Phản hồi:
{
  "status": "success",
  "hub_id": "c72b56e1-1b9a-46a8-a7b8-0a6ef27b3b72",
  "received_at": "2025-10-22T13:42:01Z"
}

