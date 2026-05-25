import os
import pickle
import face_recognition


FACE_DB_DIR = "/home/hung/restaurant_ai_robot/face_database/staff"
OUTPUT_PATH = "models/staff_faces.pkl"


def get_person_name(filename):
    """
    Ví dụ:
    lan_1.jpg  -> lan
    hung_2.jpg -> hung
    staff_a_1.jpg -> staff_a
    """
    name_without_ext = os.path.splitext(filename)[0]
    parts = name_without_ext.split("_")

    if len(parts) >= 2 and parts[-1].isdigit():
        return "_".join(parts[:-1])

    return name_without_ext


def main():
    known_encodings = []
    known_names = []

    if not os.path.exists(FACE_DB_DIR):
        print("Không thấy thư mục:", FACE_DB_DIR)
        return

    for filename in os.listdir(FACE_DB_DIR):
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        image_path = os.path.join(FACE_DB_DIR, filename)
        print("Đang xử lý:", image_path)

        image = face_recognition.load_image_file(image_path)

        face_locations = face_recognition.face_locations(image)
        face_encodings = face_recognition.face_encodings(image, face_locations)

        if len(face_encodings) == 0:
            print("Không tìm thấy khuôn mặt:", image_path)
            continue

        if len(face_encodings) > 1:
            print("Có nhiều hơn 1 khuôn mặt, bỏ qua:", image_path)
            continue

        person_name = get_person_name(filename)

        known_encodings.append(face_encodings[0])
        known_names.append(person_name)

        print("Đã encode:", person_name)

    data = {
        "encodings": known_encodings,
        "names": known_names
    }

    os.makedirs("models", exist_ok=True)

    with open(OUTPUT_PATH, "wb") as f:
        pickle.dump(data, f)

    print("Xong. Đã lưu:", OUTPUT_PATH)
    print("Tổng số ảnh encode:", len(known_encodings))


if __name__ == "__main__":
    main()