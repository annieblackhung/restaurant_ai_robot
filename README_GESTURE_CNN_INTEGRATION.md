# Gesture CNN Recognition - hand-first realistic version

Phiên bản này không ép model phải chọn `hand_raise` hoặc `thumbs_up`.
Pipeline mới:

1. Detect tay trước bằng MediaPipe.
2. Crop vùng tay.
3. CNN phân loại crop tay thành `hand_raise`, `thumbs_up`, hoặc `none`.
4. Nếu không thấy tay, confidence thấp, hoặc dự đoán mơ hồ thì trả về `none`.

Output realtime:

```python
{"gesture": "hand_raise", "confidence": 0.91, "hand_detected": True}
{"gesture": "like", "confidence": 0.88, "hand_detected": True}
{"gesture": "none", "confidence": 0.42, "hand_detected": True}
{"gesture": "none", "confidence": 0.0, "hand_detected": False}
```

`thumbs_up` được map thành `like` để tương thích với controller của nhóm.

---

## 1. Cài thư viện

```bash
pip install -r requirements_gesture_cnn.txt
```

Nếu bạn đang dùng virtualenv của project chính, chỉ cần chạy lệnh trên trong venv đó.

---

## 2. Chuẩn bị dataset raw

Cần 3 folder:

```text
data/gestures/
├── hand_raise/
├── thumbs_up/
└── none/
```

Khuyến nghị tối thiểu:

```text
hand_raise: 120 ảnh
thumbs_up : 120 ảnh
none      : 120 ảnh hoặc hơn
```

Folder `none` rất quan trọng. Nó nên gồm:

- tay thả bình thường
- nắm tay
- chỉ tay
- bàn tay úp/ngửa nhưng không phải giơ tay gọi
- tay đang cầm vật
- không có tay trong khung hình
- các tư thế dễ nhầm với thumbs up hoặc hand raise

Không đưa ảnh `hand_raise` hoặc `thumbs_up` vào folder `none`.

Có thể chụp bằng webcam:

```bash
python collect_gesture_images.py --label hand_raise --count 120
python collect_gesture_images.py --label thumbs_up --count 120
python collect_gesture_images.py --label none --count 120
```

---

## 3. Crop tay trước khi train

Để train khớp với realtime, phải tạo dataset crop tay:

```bash
python prepare_gesture_hand_crops.py --input data/gestures --output data/gestures_handcrop --clean
```

Kết quả:

```text
data/gestures_handcrop/
├── hand_raise/
├── thumbs_up/
└── none/
```

Nếu ảnh `hand_raise` hoặc `thumbs_up` bị skip vì không detect được tay, nên chụp lại ảnh đó rõ tay hơn.

---

## 4. Train CNN

CNN nhỏ, dễ chạy:

```bash
python train_gesture_cnn.py \
  --data-dir data/gestures_handcrop \
  --output models/gesture_cnn.pt \
  --model simple_cnn \
  --epochs 50 \
  --confidence-threshold 0.75 \
  --margin-threshold 0.18
```

MobileNetV2, nếu máy ổn:

```bash
python train_gesture_cnn.py \
  --data-dir data/gestures_handcrop \
  --output models/gesture_cnn.pt \
  --model mobilenet_v2 \
  --pretrained \
  --epochs 30 \
  --confidence-threshold 0.75 \
  --margin-threshold 0.18
```

Sau train sẽ có:

```text
models/gesture_cnn.pt
models/gesture_cnn.metrics.json
```

---

## 5. Test một ảnh

```bash
python test_gesture_cnn_image.py --image data/gestures/thumbs_up/thumbs_up_0001.jpg --model models/gesture_cnn.pt
```

---

## 6. Test realtime webcam

```bash
python test_gesture_cnn_realtime.py --model models/gesture_cnn.pt --show-probs
```

Nếu camera không mở:

```bash
python test_gesture_cnn_realtime.py --model models/gesture_cnn.pt --camera 1 --show-probs
```

Giải thích `reason`:

```text
no_hand_detected   : MediaPipe không thấy tay -> none
cnn_predicted_none : CNN thấy tay nhưng class là none
low_confidence     : CNN chưa đủ chắc chắn -> none
ambiguous_margin   : top1 và top2 quá sát nhau -> none
```

---

## 7. Tinh chỉnh ngưỡng nhưng không ép tỉ lệ

Nếu model quá khó nhận gesture thật:

```bash
python test_gesture_cnn_realtime.py --model models/gesture_cnn.pt --confidence-threshold 0.70 --margin-threshold 0.15 --show-probs
```

Nếu model nhận nhầm nhiều:

```bash
python test_gesture_cnn_realtime.py --model models/gesture_cnn.pt --confidence-threshold 0.80 --margin-threshold 0.22 --show-probs
```

Không nên hạ threshold quá thấp để ép ra `like`.

---

## 8. Tích hợp với project chung

Trong code camera loop:

```python
from modules.gesture_cnn_recognition import CNNGestureRecognizer, StableGestureTrigger

recognizer = CNNGestureRecognizer("models/gesture_cnn.pt")
trigger = StableGestureTrigger(window_size=8, min_hits=5, cooldown_sec=2.0)

result = recognizer.predict_frame(frame)
event = trigger.update(result)

if event:
    controller_result = controller.process_gesture_result(event)
```

Không truyền `none` vào controller. `StableGestureTrigger` đã tự bỏ qua `none`.

---

## 9. File cần nộp lên Drive

Nhóm cần copy để chạy:

```text
modules/gesture_cnn_recognition.py
models/gesture_cnn.pt
requirements_gesture_cnn.txt
README_GESTURE_CNN_INTEGRATION.md
```

Nên nộp thêm để chứng minh quá trình train:

```text
collect_gesture_images.py
prepare_gesture_hand_crops.py
train_gesture_cnn.py
test_gesture_cnn_realtime.py
test_gesture_cnn_image.py
models/gesture_cnn.metrics.json
sample_data/
```

## Troubleshooting: MediaPipe `module has no attribute solutions`

Nếu gặp lỗi:

```text
AttributeError: module 'mediapipe' has no attribute 'solutions'
```

bạn đang dùng một bản/package MediaPipe không expose API cũ `mp.solutions.hands`.
Bản patch này đã có fallback import. Nếu vẫn lỗi, cài lại MediaPipe ổn định:

```bash
pip uninstall -y mediapipe
pip install mediapipe==0.10.14
```

Kiểm tra:

```bash
python - <<'PY'
import mediapipe as mp
print(mp.__version__)
print(mp.__file__)
try:
    print(mp.solutions.hands)
except Exception as e:
    print('mp.solutions failed:', e)
    from mediapipe.python.solutions import hands
    print('fallback import OK:', hands)
PY
```
