# Bản demo thật: Camera + Microphone + Upload Audio + Excel

Bản này thay cho bản demo giả lập trước đó.

## Tính năng

- Mở giao diện robot phục vụ.
- Có nút **Bật camera Vision thật**.
- Camera hiển thị trực tiếp trong giao diện.
- Vision dùng lại logic từ `main_vision.py`: YOLO + nhận diện staff/customer.
- Có nút **Lắng nghe microphone** để nhận diện lệnh nói thật.
- Có nút **Upload audio để test** trong trường hợp microphone hoặc môi trường demo không ổn.
- Có nút **Xuất hóa đơn Excel** để lưu hóa đơn `.xlsx`.
- Vẫn giữ các nút test nhanh để backup khi model/camera gặp lỗi.

## Cách copy vào project

Giải nén zip, copy toàn bộ file vào thư mục gốc project `restaurant_ai_robot/`.

Cấu trúc đúng:

```text
restaurant_ai_robot/
├── app_demo_gui.py
├── main_ai_control_demo.py
├── main_vision.py
├── test_speech_file_ensemble.py
├── models/
│   ├── staff_faces.pkl
│   ├── speech_command_cnn.pt
│   └── speech_command_model_v3_dtw.pkl
└── modules/
    ├── ai_controller.py
    ├── action_priority.py
    ├── excel_exporter.py
    ├── gesture_mapping.py
    ├── order_manager.py
    ├── face_staff_recognition.py
    ├── speech_ensemble_recognition.py
    └── speech_mapping.py
```

## Cài thư viện

Trong venv:

```bash
pip install -r requirements_ai_control_gui_real.txt
```

Nếu `face_recognition` khó cài trên Ubuntu, cần cài trước:

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
2. Khi camera thấy khách, robot chào khách.
3. Bấm **Lắng nghe microphone** và nói: "cho tôi phở", "cho tôi bún bò", "cho tôi chai nước".
4. Nếu microphone không ổn, bấm **Upload audio để test** và chọn file `.wav/.mp3`.
5. Bấm **Xác nhận đơn** hoặc chờ module gesture thật trả về `like`.
6. Bấm **Thanh toán**.
7. Bấm **Xuất hóa đơn Excel** để lưu file hóa đơn.

## Lưu ý

- Nếu camera không mở, thử đổi camera index trong code từ `cv2.VideoCapture(0)` sang `cv2.VideoCapture(1)`.
- Nếu nút nghe thật lỗi, kiểm tra đủ 2 model:
  - `models/speech_command_cnn.pt`
  - `models/speech_command_model_v3_dtw.pkl`
- Nếu chưa có model DTW, chạy:
  ```bash
  python train_speech_command_model_v3_dtw.py
  ```
- Nút upload audio dùng cùng pipeline với microphone, chỉ khác đầu vào là file audio có sẵn.
- Nút xuất Excel cần thư viện `openpyxl`.
