# AI Controller + GUI Demo cho Robot Phục Vụ Nhà Hàng

Gói này bổ sung phần tiếp theo cho project hiện tại:

- `RestaurantAIController`: tích hợp Vision + Speech + Gesture.
- `Gesture Adapter`: nhận đầu ra `hand_raise` và `like`.
- `OrderManager`: quản lý menu, đơn gọi món, xác nhận đơn và hóa đơn.
- `Tkinter GUI`: giao diện robot cute gồm 2 mắt, 1 miệng, bên phải là menu tích chọn và hóa đơn.

## Cách copy vào project

Giả sử project hiện tại của bạn là:

```text
restaurant_ai_robot/
├── main_vision.py
├── test_speech_file_ensemble.py
├── modules/
│   ├── speech_ensemble_recognition.py
│   ├── speech_mapping.py
│   └── face_staff_recognition.py
└── models/
```

Copy các file trong gói này vào thư mục gốc project:

```text
restaurant_ai_robot/
├── app_demo_gui.py
├── main_ai_control_demo.py
└── modules/
    ├── ai_controller.py
    ├── action_priority.py
    ├── gesture_mapping.py
    └── order_manager.py
```

## Chạy demo giao diện

```bash
python main_ai_control_demo.py
```

Tkinter thường có sẵn trong Python nên demo GUI không cần cài thêm thư viện giao diện.

## Cách tích hợp module cử chỉ của bên kia

Khi bên làm gesture trả về kết quả như:

```python
gesture_result = {
    "gesture": "hand_raise",
    "confidence": 0.91
}
```

hoặc:

```python
gesture_result = {
    "gesture": "like",
    "confidence": 0.95
}
```

gọi controller:

```python
from modules.ai_controller import RestaurantAIController

controller = RestaurantAIController()

result = controller.process_gesture_result({
    "gesture": "like",
    "confidence": 0.95
})

print(result["action"])
print(result["reply"])
```

Mapping hiện tại:

```text
hand_raise / raise_hand -> CALL_STAFF
like / thumbs_up -> CONFIRM_ORDER
unknown -> UNKNOWN
```

## Cách tích hợp speech hiện tại

File `speech_ensemble_recognition.py` hiện tại đã trả về dạng:

```python
{
    "intent": "...",
    "source": "...",
    "cnn_pred": "...",
    "cnn_confidence": ...,
    "dtw_pred": "...",
    "dtw_distance": ...
}
```

Nên controller có thể nhận trực tiếp:

```python
speech_result = speech_recognizer.listen_and_predict()
controller_result = controller.process_speech_result(speech_result)
```

## Cách tích hợp vision hiện tại

Vision nên trả về output dạng:

```python
vision_result = {
    "objects": [
        {"label": "table", "confidence": 0.8, "bbox": [10, 20, 200, 300]}
    ],
    "people": [
        {"role": "customer", "name": "unknown", "confidence": 0.9, "bbox": [50, 50, 200, 360]}
    ]
}
```

Sau đó gọi:

```python
controller_result = controller.process_vision_result(vision_result)
```

## Luồng demo đề xuất khi thuyết trình

1. Bấm `Vision thấy khách`: robot chào khách.
2. Bấm `Gọi phở` hoặc tích món bên phải: hóa đơn thêm món.
3. Bấm `Like xác nhận`: trạng thái món chuyển từ chờ xác nhận sang đã xác nhận.
4. Bấm `Gọi nhân viên` hoặc `Cử chỉ giơ tay`: robot gọi nhân viên.
5. Bấm `Thanh toán`: robot đọc tổng tiền hiện tại.

## Nâng cấp tiếp theo

- Gắn camera preview vào GUI.
- Chạy vision realtime trong thread riêng.
- Chạy gesture realtime trong thread riêng.
- Thêm animation miệng khi robot nói.
- Kết nối text-to-speech để robot đọc câu trả lời.
- Xuất hóa đơn ra file JSON/PDF.
