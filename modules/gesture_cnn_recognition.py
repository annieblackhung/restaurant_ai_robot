"""
Realistic CNN gesture recognition module for Restaurant AI Robot.

Pipeline:
1) Detect a hand first with MediaPipe.
2) Crop the hand region.
3) Classify the hand crop with CNN: hand_raise / thumbs_up / none.
4) Return none when there is no hand, low confidence, or ambiguous prediction.

Public API:
    recognizer = CNNGestureRecognizer("models/gesture_cnn.pt")
    result = recognizer.predict_frame(frame_bgr)

Returned result format:
    {"gesture": "hand_raise", "confidence": 0.93, "hand_detected": True}
    {"gesture": "like", "confidence": 0.91, "hand_detected": True}
    {"gesture": "none", "confidence": 0.40, "hand_detected": True}
    {"gesture": "none", "confidence": 0.00, "hand_detected": False}

Important:
- Dataset class folder names should be: hand_raise, thumbs_up, none.
- thumbs_up is mapped to like for compatibility with the existing controller.
- StableGestureTrigger ignores none/unknown and only emits real gesture events.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image

try:
    from torchvision import models, transforms
except Exception as exc:  # pragma: no cover
    raise ImportError(
        "torchvision is required for gesture CNN. Install with: pip install torchvision"
    ) from exc


GESTURE_ALIAS = {
    "hand_raise": "hand_raise",
    "raise_hand": "hand_raise",
    "thumbs_up": "like",
    "thumb_up": "like",
    "like": "like",
    "none": "none",
    "no_gesture": "none",
    "background": "none",
    "other": "none",
    "unknown": "none",
}

NONE_LABELS = {"none", "no_gesture", "background", "other", "unknown"}

def draw_hand_attention_frame(frame_bgr: np.ndarray, bbox: List[int]) -> np.ndarray:
    """
    Keep the full frame, but highlight the detected hand region.

    Why:
    - hand_raise is not only a hand shape; it also depends on hand position.
    - If we crop only the hand, the CNN loses the fact that the hand is raised.
    - This keeps global position while still telling the CNN where the hand is.
    """
    if frame_bgr is None or frame_bgr.size == 0 or bbox is None:
        return frame_bgr

    height, width = frame_bgr.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in bbox]

    x1 = max(0, min(width - 1, x1))
    x2 = max(0, min(width - 1, x2))
    y1 = max(0, min(height - 1, y1))
    y2 = max(0, min(height - 1, y2))

    if x2 <= x1 or y2 <= y1:
        return frame_bgr.copy()

    # Darken the whole image, then paste the hand region back.
    # The CNN sees full-frame position + clear hand area.
    out = (frame_bgr.astype(np.float32) * 0.35).astype(np.uint8)
    out[y1:y2 + 1, x1:x2 + 1] = frame_bgr[y1:y2 + 1, x1:x2 + 1]

    # Draw a rectangle so the model consistently knows the detected hand region.
    cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 3)

    cx = int((x1 + x2) / 2)
    cy = int((y1 + y2) / 2)
    cv2.circle(out, (cx, cy), 5, (0, 255, 0), -1)

    return out

class SimpleGestureCNN(nn.Module):
    """Small CNN fallback. Good for same-camera demo datasets."""

    def __init__(self, num_classes: int):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(0.35),
            nn.Linear(256, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        return self.classifier(x)


def build_model(model_name: str, num_classes: int) -> nn.Module:
    model_name = model_name.lower()
    if model_name == "mobilenet_v2":
        model = models.mobilenet_v2(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(in_features, num_classes)
        return model
    if model_name == "simple_cnn":
        return SimpleGestureCNN(num_classes=num_classes)
    raise ValueError(f"Unsupported model_name={model_name!r}. Use simple_cnn or mobilenet_v2.")


class HandCropper:
    """Detects hand(s) and returns the largest hand crop from a BGR frame."""

    def __init__(
        self,
        max_num_hands: int = 2,
        min_detection_confidence: float = 0.55,
        min_tracking_confidence: float = 0.50,
        padding_ratio: float = 0.45,
        static_image_mode: bool = False,
    ) -> None:
        try:
            import mediapipe as mp
        except Exception as exc:  # pragma: no cover
            raise ImportError(
                "mediapipe is required for hand-first gesture recognition. "
                "Install with: pip install mediapipe"
            ) from exc

        self.padding_ratio = padding_ratio

        # MediaPipe has had multiple Python package layouts. Some environments
        # expose Hands at mp.solutions.hands, while others do not attach the
        # `solutions` attribute to the top-level mediapipe module. Try both so
        # the module works on more Linux/venv setups.
        try:
            self.mp_hands = mp.solutions.hands
        except AttributeError:
            try:
                from mediapipe.python.solutions import hands as mp_hands
                self.mp_hands = mp_hands
            except Exception as exc:  # pragma: no cover
                mp_file = getattr(mp, "__file__", "unknown")
                mp_version = getattr(mp, "__version__", "unknown")
                raise ImportError(
                    "Your mediapipe package does not expose the legacy Hands API.\n"
                    f"Detected mediapipe version: {mp_version}\n"
                    f"Detected mediapipe path: {mp_file}\n"
                    "Fix it with:\n"
                    "  pip uninstall -y mediapipe\n"
                    "  pip install mediapipe==0.10.14"
                ) from exc

        self.hands = self.mp_hands.Hands(
            static_image_mode=static_image_mode,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def crop_largest_hand(
        self, frame_bgr: np.ndarray
    ) -> Tuple[Optional[np.ndarray], Optional[List[int]], float]:
        if frame_bgr is None or frame_bgr.size == 0:
            return None, None, 0.0

        height, width = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self.hands.process(rgb)

        if not result.multi_hand_landmarks:
            return None, None, 0.0

        best_bbox: Optional[List[int]] = None
        best_area = -1
        best_score = 0.0

        handedness_list = result.multi_handedness or []
        for idx, hand_landmarks in enumerate(result.multi_hand_landmarks):
            xs = [lm.x for lm in hand_landmarks.landmark]
            ys = [lm.y for lm in hand_landmarks.landmark]
            x1 = int(max(0, min(xs) * width))
            y1 = int(max(0, min(ys) * height))
            x2 = int(min(width - 1, max(xs) * width))
            y2 = int(min(height - 1, max(ys) * height))

            box_w = max(1, x2 - x1)
            box_h = max(1, y2 - y1)
            pad = int(max(box_w, box_h) * self.padding_ratio)
            x1 = max(0, x1 - pad)
            y1 = max(0, y1 - pad)
            x2 = min(width - 1, x2 + pad)
            y2 = min(height - 1, y2 + pad)
            area = max(1, (x2 - x1) * (y2 - y1))

            score = 1.0
            if idx < len(handedness_list) and handedness_list[idx].classification:
                score = float(handedness_list[idx].classification[0].score)

            if area > best_area:
                best_area = area
                best_bbox = [x1, y1, x2, y2]
                best_score = score

        if best_bbox is None:
            return None, None, 0.0

        x1, y1, x2, y2 = best_bbox
        crop = frame_bgr[y1 : y2 + 1, x1 : x2 + 1].copy()
        if crop.size == 0:
            return None, None, 0.0
        return crop, best_bbox, best_score


@dataclass
class CNNGestureRecognizer:
    model_path: str = "models/gesture_cnn.pt"
    image_size: int = 224
    confidence_threshold: float = 0.75
    margin_threshold: float = 0.18
    input_mode: str = "full_frame_with_hand_box"
    use_hand_detector: bool = True
    hand_detection_confidence: float = 0.55
    hand_padding_ratio: float = 0.45
    device: Optional[str] = None

    def __post_init__(self) -> None:
        self.device_obj = torch.device(
            self.device if self.device else ("cuda" if torch.cuda.is_available() else "cpu")
        )
        checkpoint_path = Path(self.model_path)
        if not checkpoint_path.exists():
            raise FileNotFoundError(
                f"Gesture model not found: {checkpoint_path}. Train it first with train_gesture_cnn.py"
            )

        checkpoint = torch.load(checkpoint_path, map_location=self.device_obj)
        self.class_names: List[str] = checkpoint["class_names"]
        self.model_name: str = checkpoint.get("model_name", "simple_cnn")
        self.image_size = int(checkpoint.get("image_size", self.image_size))
        self.confidence_threshold = float(
            checkpoint.get("confidence_threshold", self.confidence_threshold)
        )
        self.margin_threshold = float(checkpoint.get("margin_threshold", self.margin_threshold))
        self.input_mode = str(checkpoint.get("input_mode", self.input_mode))
        self.use_hand_detector = bool(checkpoint.get("use_hand_detector", self.use_hand_detector))
        self.hand_detection_confidence = float(
            checkpoint.get("hand_detection_confidence", self.hand_detection_confidence)
        )
        self.hand_padding_ratio = float(checkpoint.get("hand_padding_ratio", self.hand_padding_ratio))

        self.model = build_model(self.model_name, num_classes=len(self.class_names))
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.to(self.device_obj)
        self.model.eval()

        self.transform = transforms.Compose(
            [
                transforms.Resize((self.image_size, self.image_size)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ]
        )

        self.hand_cropper: Optional[HandCropper] = None
        if self.use_hand_detector:
            self.hand_cropper = HandCropper(
                min_detection_confidence=self.hand_detection_confidence,
                padding_ratio=self.hand_padding_ratio,
                static_image_mode=False,
            )

    def _none_result(
        self,
        confidence: float = 0.0,
        reason: str = "none",
        hand_detected: bool = False,
        bbox: Optional[List[int]] = None,
        probabilities: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        return {
            "gesture": "none",
            "confidence": float(confidence),
            "hand_detected": bool(hand_detected),
            "hand_bbox": bbox,
            "reason": reason,
            "probabilities": probabilities or {},
        }

    def predict_frame(self, frame_bgr: np.ndarray) -> Dict[str, Any]:
        if frame_bgr is None or frame_bgr.size == 0:
            return self._none_result(reason="empty_frame")

        hand_detected = False
        hand_bbox: Optional[List[int]] = None
        model_input = frame_bgr

        if self.hand_cropper is not None:
            crop, bbox, hand_score = self.hand_cropper.crop_largest_hand(frame_bgr)
            if crop is None:
                return self._none_result(reason="no_hand_detected", hand_detected=False)
            hand_detected = True
            hand_bbox = bbox
                           
            if self.input_mode == "hand_crop":
                model_input = crop
            elif self.input_mode == "full_frame_with_hand_box":
                model_input = draw_hand_attention_frame(frame_bgr, bbox)
            else:
                model_input = frame_bgr
        else:
            hand_detected = True

        rgb = cv2.cvtColor(model_input, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        x = self.transform(image).unsqueeze(0).to(self.device_obj)

        with torch.no_grad():
            logits = self.model(x)
            probs_tensor = torch.softmax(logits, dim=1)[0]
            sorted_probs, sorted_indices = torch.sort(probs_tensor, descending=True)

        top_conf = float(sorted_probs[0].item())
        top_idx = int(sorted_indices[0].item())
        second_conf = float(sorted_probs[1].item()) if len(sorted_probs) > 1 else 0.0
        margin = top_conf - second_conf

        raw_label = self.class_names[top_idx]
        mapped_label = GESTURE_ALIAS.get(raw_label, raw_label)
        probabilities = {
            GESTURE_ALIAS.get(self.class_names[i], self.class_names[i]): float(probs_tensor[i].item())
            for i in range(len(self.class_names))
        }

        if mapped_label in NONE_LABELS:
            return self._none_result(
                confidence=top_conf,
                reason="cnn_predicted_none",
                hand_detected=hand_detected,
                bbox=hand_bbox,
                probabilities=probabilities,
            )

        if top_conf < self.confidence_threshold:
            return self._none_result(
                confidence=top_conf,
                reason="low_confidence",
                hand_detected=hand_detected,
                bbox=hand_bbox,
                probabilities=probabilities,
            )

        if margin < self.margin_threshold:
            return self._none_result(
                confidence=top_conf,
                reason="ambiguous_margin",
                hand_detected=hand_detected,
                bbox=hand_bbox,
                probabilities=probabilities,
            )

        return {
            "gesture": mapped_label,
            "confidence": top_conf,
            "hand_detected": hand_detected,
            "hand_bbox": hand_bbox,
            "margin": margin,
            "probabilities": probabilities,
        }


class StableGestureTrigger:
    """
    Converts frame-by-frame predictions into one stable event.

    It intentionally ignores none/unknown so the system does not trigger an action
    just because a hand exists or because the CNN is unsure.
    """

    def __init__(self, window_size: int = 8, min_hits: int = 5, cooldown_sec: float = 2.0):
        self.window_size = window_size
        self.min_hits = min_hits
        self.cooldown_sec = cooldown_sec
        self.history: Deque[Dict[str, Any]] = deque(maxlen=window_size)
        self.last_trigger_at = 0.0

    def update(self, result: Dict[str, Any]) -> Optional[Dict[str, float | str]]:
        gesture = str(result.get("gesture", "none"))
        confidence = float(result.get("confidence", 0.0))
        self.history.append({"gesture": gesture, "confidence": confidence})

        now = time.time()
        if now - self.last_trigger_at < self.cooldown_sec:
            return None

        valid = [r for r in self.history if r["gesture"] not in {"none", "unknown"}]
        if len(valid) < self.min_hits:
            return None

        counts: Dict[str, int] = {}
        confidences: Dict[str, List[float]] = {}
        for item in valid:
            label = str(item["gesture"])
            counts[label] = counts.get(label, 0) + 1
            confidences.setdefault(label, []).append(float(item["confidence"]))

        best_label, best_count = max(counts.items(), key=lambda kv: kv[1])
        if best_count < self.min_hits:
            return None

        avg_conf = float(sum(confidences[best_label]) / len(confidences[best_label]))
        self.last_trigger_at = now
        self.history.clear()
        return {"gesture": best_label, "confidence": avg_conf}
