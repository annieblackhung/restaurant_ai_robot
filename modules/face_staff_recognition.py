import pickle
import cv2
import numpy as np
import face_recognition


class StaffFaceRecognizer:
    def __init__(self, encoding_path="models/staff_faces.pkl", tolerance=0.45):
        self.encoding_path = encoding_path
        self.tolerance = tolerance

        with open(self.encoding_path, "rb") as f:
            data = pickle.load(f)

        self.known_encodings = data["encodings"]
        self.known_names = data["names"]

        print("Loaded staff faces:", len(self.known_names))

    def recognize(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb)
        face_encodings = face_recognition.face_encodings(rgb, face_locations)

        results = []

        for location, encoding in zip(face_locations, face_encodings):
            top, right, bottom, left = location

            role = "customer"
            name = "unknown"
            distance_value = None

            if len(self.known_encodings) > 0:
                distances = face_recognition.face_distance(
                    self.known_encodings,
                    encoding
                )

                best_index = int(np.argmin(distances))
                best_distance = float(distances[best_index])
                distance_value = best_distance

                if best_distance < self.tolerance:
                    role = "staff"
                    name = self.known_names[best_index]

            results.append({
                "role": role,
                "name": name,
                "distance": distance_value,
                "bbox": [left, top, right, bottom]
            })

        return results

    def draw(self, frame, results):
        for face in results:
            x1, y1, x2, y2 = face["bbox"]
            role = face["role"]
            name = face["name"]
            distance = face["distance"]

            if role == "staff":
                color = (0, 255, 0)
            else:
                color = (0, 165, 255)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            if distance is not None:
                text = f"{role}: {name} {distance:.2f}"
            else:
                text = f"{role}: {name}"

            cv2.putText(
                frame,
                text,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2
            )

        return frame