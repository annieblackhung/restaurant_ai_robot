# Bản demo thật V2: Camera + Speech + Upload Audio + QR Payment + Excel cố định

## Những thay đổi chính

- Xóa khỏi menu:
  - Cà phê sữa
  - Trà đá
  - Chả giò
- Chỉ giữ:
  - Phở bò
  - Bún bò
  - Chai nước
- File Excel cố định:
  - `data/hoa_don_robot_demo.xlsx`
- Khi bấm **Xác nhận đơn**, app tự ghi hóa đơn vào file Excel cố định.
- Khi bấm **Thanh toán bằng QR**, app hiện QR.
- Quét QR bằng điện thoại sẽ mở trang web demo có nút **Xác nhận đã thanh toán**.
- Khi bấm xác nhận trên điện thoại:
  - GUI nhận trạng thái đã thanh toán.
  - File Excel được cập nhật sheet lịch sử thanh toán.
  - Hóa đơn trên GUI được reset.
- Có nút backup **Xác nhận đã thanh toán trên máy demo** trong cửa sổ QR nếu điện thoại không cùng Wi-Fi.

## Cách copy vào project

Giải nén zip, copy toàn bộ file vào thư mục gốc project `restaurant_ai_robot/`.

Cấu trúc đúng:

```text
restaurant_ai_robot/
├── app_demo_gui.py
├── main_ai_control_demo.py
├── requirements_ai_control_gui_real.txt
├── data/
│   └── hoa_don_robot_demo.xlsx
├── modules/
│   ├── ai_controller.py
│   ├── action_priority.py
│   ├── excel_exporter.py
│   ├── gesture_mapping.py
│   ├── order_manager.py
│   ├── payment_qr_server.py
│   ├── face_staff_recognition.py
│   ├── speech_ensemble_recognition.py
│   └── speech_mapping.py
└── models/
    ├── staff_faces.pkl
    ├── speech_command_cnn.pt
    └── speech_command_model_v3_dtw.pkl
```

Lưu ý: zip chỉ chứa các file mới/sửa. Các file cũ như `main_vision.py`, `face_staff_recognition.py`, `speech_ensemble_recognition.py`, `speech_mapping.py` vẫn giữ nguyên trong project của bạn.

## Cài thư viện

```bash
pip install -r requirements_ai_control_gui_real.txt
```

Nếu `face_recognition` khó cài trên Ubuntu:

```bash
sudo apt update
sudo apt install -y cmake build-essential
pip install dlib face_recognition
```

## Chạy demo

```bash
python main_ai_control_demo.py
```

## Luồng demo khuyến nghị

1. Bấm **Bật camera Vision thật**.
2. Bấm **Lắng nghe microphone** hoặc **Upload audio để test** để thêm món.
3. Bấm **Xác nhận đơn + ghi Excel**.
4. Mở file `data/hoa_don_robot_demo.xlsx` để thấy hóa đơn hiện tại.
5. Bấm **Thanh toán bằng QR**.
6. Quét QR bằng điện thoại.
7. Trên điện thoại, bấm **Xác nhận đã thanh toán**.
8. Quay lại GUI:
   - Hóa đơn reset.
   - Excel có lịch sử thanh toán.

## Nếu điện thoại quét QR không mở được

Điện thoại và laptop cần cùng Wi-Fi. Nếu vẫn không được:

- Tắt firewall tạm thời.
- Hoặc dùng nút backup trong cửa sổ QR:
  - **Xác nhận đã thanh toán trên máy demo**

## File Excel gồm các sheet

- `HoaDonHienTai`: hóa đơn hiện tại.
- `LichSuThanhToan`: lịch sử các lần thanh toán.
- `ChiTietDaThanhToan`: chi tiết món đã thanh toán.
- `EventLog`: log sự kiện demo.
