# Patch tích hợp Gesture CNN vào bản demo V2

Patch này thêm Gesture CNN vào camera loop hiện có của `app_demo_gui.py`.

## File trong patch

```text
app_demo_gui.py
modules/gesture_cnn_recognition.py
models/gesture_cnn.pt
models/gesture_cnn.metrics.json
requirements_gesture_cnn.txt
requirements_ai_control_gui_real.txt
README_GESTURE_CNN_INTEGRATION.md
```

## Cách copy vào project

Trong thư mục giải nén patch, chạy:

```bash
cp app_demo_gui.py ~/restaurant_ai_robot/
cp modules/gesture_cnn_recognition.py ~/restaurant_ai_robot/modules/
mkdir -p ~/restaurant_ai_robot/models
cp models/gesture_cnn.pt ~/restaurant_ai_robot/models/
cp models/gesture_cnn.metrics.json ~/restaurant_ai_robot/models/
cp requirements_gesture_cnn.txt ~/restaurant_ai_robot/
cp requirements_ai_control_gui_real.txt ~/restaurant_ai_robot/
cp README_GESTURE_CNN_INTEGRATION.md ~/restaurant_ai_robot/
```

Cài thư viện trong venv:

```bash
cd ~/restaurant_ai_robot
source venv/bin/activate
pip install -r requirements_gesture_cnn.txt
```

Nếu MediaPipe lỗi trên Ubuntu, thử:

```bash
pip uninstall -y mediapipe
pip install mediapipe==0.10.14
```

## Chạy

```bash
python main_ai_control_demo.py
```

Bấm nút:

```text
Bật camera Vision + Gesture
```

Khi camera đang bật:

- YOLO + Face Recognition vẫn chạy như cũ.
- Gesture CNN sẽ tự nhận `hand_raise` hoặc `like`.
- `hand_raise` -> controller gọi nhân viên.
- `like` -> controller xác nhận đơn và tự cập nhật Excel.
- `none` sẽ bị bỏ qua, không truyền vào controller.

## Test riêng gesture

```bash
python test_gesture_cnn_realtime.py --model models/gesture_cnn.pt --show-probs
```
