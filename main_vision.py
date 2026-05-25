from ultralytics import YOLO
import cv2

from modules.face_staff_recognition import StaffFaceRecognizer


# =========================
# Cấu hình
# =========================

YOLO_MODEL = "yolov8n.pt"
FACE_MODEL = "models/staff_faces.pkl"

CONF_THRESHOLD = 0.5

TARGET_CLASSES = {
    "person",
    "chair",
    "dining table",
    "bottle",
    "cup"
}


# =========================
# Hàm vẽ YOLO
# =========================

def draw_yolo_objects(frame, yolo_results, model):
    detections = []

    for result in yolo_results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            label = model.names[cls_id]
            confidence = float(box.conf[0])

            if label not in TARGET_CLASSES:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])

            display_label = "table" if label == "dining table" else label

            detections.append({
                "label": display_label,
                "confidence": confidence,
                "bbox": [x1, y1, x2, y2]
            })

            if display_label == "person":
                color = (255, 0, 0)
            else:
                color = (0, 255, 0)

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                color,
                2
            )

            cv2.putText(
                frame,
                f"{display_label} {confidence:.2f}",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2
            )

    return frame, detections


# =========================
# Ghép face vào person
# =========================

def assign_face_to_persons(yolo_detections, face_results):
    people = []

    for det in yolo_detections:
        if det["label"] != "person":
            continue

        px1, py1, px2, py2 = det["bbox"]

        assigned_face = None

        for face in face_results:
            fx1, fy1, fx2, fy2 = face["bbox"]

            face_center_x = (fx1 + fx2) // 2
            face_center_y = (fy1 + fy2) // 2

            if px1 <= face_center_x <= px2 and py1 <= face_center_y <= py2:
                assigned_face = face
                break

        if assigned_face:
            role = assigned_face["role"]
            name = assigned_face["name"]
            distance = assigned_face["distance"]
        else:
            role = "customer"
            name = "unknown"
            distance = None

        people.append({
            "role": role,
            "name": name,
            "distance": distance,
            "bbox": det["bbox"],
            "confidence": det["confidence"]
        })

    return people


# =========================
# Vẽ role staff/customer dưới bbox người
# =========================

def draw_people_roles(frame, people):
    for person in people:
        x1, y1, x2, y2 = person["bbox"]
        role = person["role"]
        name = person["name"]

        if role == "staff":
            color = (0, 255, 255)
        else:
            color = (0, 165, 255)

        text = f"{role}: {name}"

        cv2.putText(
            frame,
            text,
            (x1, y2 + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2
        )

    return frame


# =========================
# Main
# =========================

def main():
    print("Loading YOLO model...")
    yolo_model = YOLO(YOLO_MODEL)

    print("Loading face recognition model...")
    face_ai = StaffFaceRecognizer(
        encoding_path=FACE_MODEL,
        tolerance=0.45
    )

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Không mở được camera")
        return

    while True:
        ret, frame = cap.read()

        if not ret:
            print("Không đọc được frame")
            break

        # 1. YOLO nhận diện vật thể/người
        yolo_results = yolo_model(
            frame,
            conf=CONF_THRESHOLD,
            verbose=False
        )

        frame, yolo_detections = draw_yolo_objects(
            frame,
            yolo_results,
            yolo_model
        )

        # 2. Face Recognition nhận diện staff/customer
        face_results = face_ai.recognize(frame)

        frame = face_ai.draw(frame, face_results)

        # 3. Ghép khuôn mặt với bbox person
        people = assign_face_to_persons(
            yolo_detections,
            face_results
        )

        frame = draw_people_roles(frame, people)

        # 4. In output ra terminal
        output = {
            "objects": [
                obj for obj in yolo_detections
                if obj["label"] != "person"
            ],
            "people": people
        }

        print(output)

        cv2.imshow("YOLOv8 + Staff Customer Recognition", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
