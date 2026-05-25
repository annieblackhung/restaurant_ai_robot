# Restaurant AI Robot

Dự án xây dựng hệ thống AI cho robot phục vụ thông minh trong nhà hàng.

## Chức năng hiện tại

- Nhận diện vật thể bằng YOLOv8:
  - person
  - chair
  - dining table
  - bottle
  - cup

- Nhận diện người:
  - staff
  - customer

- Nhận diện lệnh giọng nói:
  - call_staff
  - order_water
  - order_pho
  - order_bun_bo
  - payment

## Công nghệ sử dụng

- Python
- OpenCV
- YOLOv8
- Face Recognition
- Librosa
# Restaurant AI Robot

Dự án xây dựng hệ thống AI cho robot phục vụ thông minh trong nhà hàng.

## Chức năng hiện tại

- Nhận diện vật thể bằng YOLOv8:
  - person
  - chair
  - dining table
  - bottle
  - cup

- Nhận diện người:
  - staff
  - customer

- Nhận diện lệnh giọng nói:
  - call_staff
  - order_water
  - order_pho
  - order_bun_bo
  - payment

## Công nghệ sử dụng

- Python
- OpenCV
- YOLOv8
- Face Recognition
- Librosa
- Scikit-learn
- RandomForest
- SoundDevice

## Cài đặt

```bash
git clone <repo_url>
cd restaurant_ai_robot

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
