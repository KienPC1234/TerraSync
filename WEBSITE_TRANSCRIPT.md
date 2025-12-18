# 📝 Bản ghi & Đánh giá Website TerraSync

Tài liệu này cung cấp hướng dẫn và tóm tắt về các trang trong ứng dụng TerraSync, được tạo ra từ mã nguồn.

## 📌 Bảng Điều Khiển (`dashboard.py`)
**Vai trò:** Trung tâm điều khiển & Tổng quan
**Giao diện:**
- **Chỉ số hàng đầu:** Bố cục 4 cột hiển thị *Nhiệt độ không khí*, *Độ ẩm đất*, *Lượng mưa*, và *Tốc độ gió* cùng với sự thay đổi (delta) so với lần đọc trước.
- **Tổng quan trang trại:**
  - *Biểu đồ tròn:* Phân bố cây trồng theo diện tích.
  - *Thống kê:* Bảng tổng diện tích canh tác.
- **Bản đồ tương tác:** Hiển thị tất cả các vườn (đa giác) với mã màu dựa trên lựa chọn. Popup hiển thị loại cây và trạng thái.
- **Bảng chi tiết vườn:** Khung chứa (giống thanh bên) hiển thị chi tiết cụ thể cho một vườn được chọn:
  - *Chỉ số:* Trạng thái (Đủ nước/Thiếu nước), Lượng nước dùng hàng ngày, Đếm ngược ngày thu hoạch.
  - *Dữ liệu cảm biến trực tiếp:* Nhiệt độ & Độ ẩm đất nếu có node được liên kết.
  - *Thanh tiến độ:* % tiến độ tưới.
- **Mô phỏng 3D:** Iframe nhúng mô phỏng khu vườn 3D phản ứng với các biến môi trường.
- **Biểu đồ:** Biểu đồ đường hiển thị xu hướng Độ ẩm đất, Nhiệt độ không khí và Độ ẩm theo thời gian.
- **Bảng cảnh báo:** Danh sách các cảnh báo đang hoạt động (Nghiêm trọng/Cảnh báo/Thông tin).

---

## 🌾 Vườn Của Tôi (`my_fields.py`)
**Vai trò:** Danh sách quản lý vườn
**Giao diện:**
- **Thẻ trạng thái:** Ba hộp tóm tắt ở trên cùng hiển thị số lượng công việc tưới *Đã hoàn thành*, *Đang hoạt động*, và *Chờ xử lý*.
- **Thanh hành động:** Nút "Thêm vườn" và nút "Cập nhật trạng thái" (kích hoạt tính toán lại dựa trên dữ liệu cảm biến trực tiếp).
- **Danh sách vườn (Thẻ):** Mỗi vườn được hiển thị dưới dạng thẻ chi tiết chứa:
  - *Bản đồ nhỏ:* Hình thu nhỏ của đa giác vườn.
  - *Thông tin:* Tên, Diện tích, Huy hiệu trạng thái (Xanh/Cam/Đỏ), Nhu cầu nước (m³), Loại cây, Giai đoạn.
  - *Thời gian & Tiến độ:* Thời gian ước tính cần thiết và chỉ báo tiến độ hình tròn.
  - *Hành động:* Các nút Chỉnh sửa và Xóa.
- **Modal Chỉnh sửa:** Form để sửa đổi tên, loại cây, giai đoạn, và ghi đè thủ công trạng thái/tiến độ.

---

## 📍 Thêm Vườn (`add_field.py`)
**Vai trò:** Trình hướng dẫn tạo vườn mới
**Luồng hoạt động:**
1.  **Bước 1: Vị trí trung tâm:**
    - Bản đồ tương tác để ghim tâm của vườn mới.
    - Các trường nhập liệu thủ công cho Vĩ độ/Kinh độ.
2.  **Bước 2: Xác định ranh giới:**
    - **Tab 1: Vẽ thủ công:** Sử dụng công cụ vẽ để xác định đa giác.
    - **Tab 2: Phát hiện bằng AI:** Vẽ một hộp giới hạn, sau đó gọi API AI (Roboflow/Sentinel-2) để tự động phân đoạn các ruộng cây trồng. Trả về nhiều đa giác được phát hiện để lựa chọn.
3.  **Bước 3: Chi tiết & Lưu:**
    - Nhập Tên.
    - Chọn Loại cây & Giai đoạn phát triển (Tự động cập nhật hệ số $K_c$ và nhiệt độ tối ưu).
    - Nút "Lưu" cam kết dữ liệu vào DB và tính toán nhu cầu nước ban đầu.

---

## 📅 Lịch Trình (`my_schedule.py`)
**Vai trò:** Kế hoạch tưới tiêu & Dự báo
**Giao diện:**
- **Hành động toàn cục:** Nút "Tính toán nhu cầu hôm nay" chạy logic cho tất cả các vườn.
- **Bảng dữ liệu NASA:** Expander hiển thị lịch sử thời tiết 30 ngày và tính toán **ET0 (Thoát hơi nước)** sử dụng phương trình Penman-Monteith.
- **Các Tab:**
  1.  **Trạng thái hiện tại:** Bảng điều khiển trạng thái trực tiếp. So sánh giá trị DB với tính toán Cảm biến trực tiếp. Hiển thị các chỉ số về Nước cần, Thời gian cần, và Tiến độ.
  2.  **Dự báo 7 ngày:**
      - Sử dụng Hồi quy tuyến tính trên độ ẩm đất lịch sử để dự đoán xu hướng.
      - Hiển thị Biểu đồ cột về nhu cầu nước dự đoán cho tuần tới.
      - Các chỉ số về Tổng cộng, Trung bình, và Cao điểm sử dụng nước.
  3.  **Cài đặt:**
      - Cấu hình cho Hiệu quả tưới, Tần suất, và Thời gian ưu tiên.
      - Biểu đồ đường của dữ liệu cảm biến lịch sử.

---

## 🛰️ Xem Vệ Tinh (`satellite_view.py`)
**Vai trò:** Viễn thám & Phân tích sức khỏe
**Các Tab:**
1.  **Bản đồ:** Chọn một vườn để xem. Nút "Quét Vệ Tinh Ngay" gọi API backend để lấy hình ảnh Sentinel-2.
2.  **Phân tích NDVI:**
    - **Giao diện:** Hiển thị bản đồ NDVI đã xử lý (Bản đồ nhiệt: Đỏ-Vàng-Xanh) và ảnh màu thực tế được AI nâng cấp (Upscaled).
    - **Thống kê:** Các chỉ số cho NDVI Trung bình/Cao nhất.
    - **Biểu đồ:** Biểu đồ tròn (Phân bố sức khỏe) và Biểu đồ tần suất (Phân bố giá trị pixel).
3.  **Thời tiết & Khuyến nghị:**
    - Hiển thị dự báo hàng ngày trong 7 ngày và biểu đồ hàng giờ trong 48 giờ (Nhiệt độ, Mưa, Gió).
    - **Thông tin AI:** "CropNet AI" phân tích dữ liệu thời tiết để đưa ra các khuyến nghị canh tác cụ thể.

---

## 🤖 Phát Hiện Bệnh Bằng AI (`ai_field_detection.py`)
**Vai trò:** Chẩn đoán bệnh cây trồng
**Các Tab:**
1.  **Chẩn đoán:**
    - Tải ảnh lên.
    - **Tùy chọn:** Chọn Chế độ (Phân loại vs Phát hiện), Loại cây, Bộ phận (Lá/Quả), Giai đoạn.
    - **Xử lý:** Gửi ảnh đến Gemini 2.5 Flash để phân tích chi tiết.
    - **Đầu ra:** Trả về Tên bệnh, Độ tin cậy, Mức độ nghiêm trọng, Gợi ý điều trị, và Mẹo phòng ngừa. Hỗ trợ hiển thị Hộp giới hạn trong chế độ Phát hiện.
2.  **Kết quả phân tích:** Danh sách lịch sử các chẩn đoán trước đây và thống kê về mức độ tin cậy của AI.

---

## 💬 Trợ Lý AI (`chat.py`)
**Vai trò:** Trợ lý ảo (CropNet AI)
**Giao diện:**
- **Thanh bên:** Quản lý lịch sử trò chuyện (Lưu/Tải/Xóa phiên).
- **Bộ chọn ngữ cảnh:** Dropdown để chọn một vườn cụ thể.
- **Tiêm ngữ cảnh trực tiếp:** Tự động đưa dữ liệu tĩnh của vườn (Diện tích, Cây trồng) VÀ **Dữ liệu Telemetry trực tiếp** (Độ ẩm đất, Mưa, Nhiệt độ) vào system prompt.
- **Giao diện Chat:** Giao diện chat tiêu chuẩn. Hỗ trợ **Tải ảnh lên** để Gemini phân tích hình ảnh.

---

## 🔧 Quản Lý IoT (`iot_management.py`)
**Vai trò:** Cấu hình phần cứng
**Các Tab:**
1.  **Hubs:** Danh sách các Hub đã đăng ký (Trạng thái Online/Offline). Đăng ký Hub mới.
2.  **Cảm biến:** Xem các node cảm biến cụ thể (Đất/Khí quyển) được liên kết với Hub. Hiển thị các lần đọc mới nhất.
3.  **Dữ liệu thời gian thực:** Xem trực tiếp dữ liệu telemetry thô với tính năng tự động làm mới. Bao gồm biểu đồ xu hướng (Plotly) cho 24h qua.
4.  **Cảnh báo:** Lịch sử cảnh báo hệ thống (Nghiêm trọng/Cảnh báo).
5.  **Cài đặt:** Cấu hình tần số RF (433MHz), Khoảng thời gian lấy mẫu (Polling), Ngưỡng pin, và Thời gian ngủ cho các node.

---

## 💧 Điều Khiển Tưới (`irrigation_control.py`)
**Vai trò:** Điều khiển Van & Máy bơm
**Giao diện:**
- Danh sách Thiết bị (Van/Máy bơm).
- **Điều khiển thủ công:** Công tắc Bật/Tắt đơn giản.
- **Cấu hình Tự động hóa:**
  - Bật "Chế độ Tự động".
  - Xây dựng Logic: *Nếu [Cảm biến X] [Biến Y] là [Trên/Dưới] [Ngưỡng], thì Kích hoạt.*

---

## 🔐 Đăng Nhập (`login.py`)
**Vai trò:** Xác thực
- Trang đích đơn giản giải thích về hệ thống.
- Nút "Đăng nhập bằng Google".

---

## ⚙️ Cài Đặt (`settings.py`) (Tóm tắt)
**Vai trò:** Cấu hình Người dùng & Ứng dụng
- **Hồ sơ:** Tên, Vai trò, Kinh nghiệm, Tiểu sử.
- **Vị trí:** Tọa độ trang trại mặc định, Múi giờ, Đơn vị đo.
- **Tùy chọn:** Chủ đề, Cài đặt thông báo (Email/Push/OneSignal).
- **Bảo mật:** Xuất/Xóa dữ liệu tài khoản.
- **Bảng quản trị:** (Nếu là admin) Quản lý cơ sở dữ liệu Người dùng và Cây trồng.

---

## 🆘 Trung Tâm Trợ Giúp (`help_center.py`) (Tóm tắt)
**Vai trò:** Hỗ trợ & Tài liệu
- **Trợ lý AI:** Chat chuyên dụng cho trợ giúp chung.
- **Tài liệu:** Hướng dẫn thêm vườn, thiết lập IoT, sử dụng API.
- **Thư viện cây trồng:** Cơ sở dữ liệu có thể tìm kiếm về các loại cây được hỗ trợ và thông số của chúng ($K_c$, Giai đoạn).
- **Khắc phục sự cố:** FAQ và Kiểm tra sức khỏe hệ thống (Kết nối DB, API key).
- **Liên hệ:** Form hỗ trợ.