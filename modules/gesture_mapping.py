GESTURE_TO_ACTION = {
    "hand_raise": {
        "source": "gesture",
        "gesture": "hand_raise",
        "intent": "call_staff",
        "action": "CALL_STAFF",
        "reply": "Dạ, tôi sẽ gọi nhân viên đến hỗ trợ quý khách."
    },
    "raise_hand": {
        "source": "gesture",
        "gesture": "raise_hand",
        "intent": "call_staff",
        "action": "CALL_STAFF",
        "reply": "Dạ, tôi sẽ gọi nhân viên đến hỗ trợ quý khách."
    },
    "like": {
        "source": "gesture",
        "gesture": "like",
        "intent": "confirm",
        "action": "CONFIRM_ORDER",
        "reply": "Dạ, tôi đã xác nhận đơn gọi món."
    },
    "thumbs_up": {
        "source": "gesture",
        "gesture": "thumbs_up",
        "intent": "confirm",
        "action": "CONFIRM_ORDER",
        "reply": "Dạ, tôi đã xác nhận đơn gọi món."
    },
    "unknown": {
        "source": "gesture",
        "gesture": "unknown",
        "intent": "unknown",
        "action": "UNKNOWN",
        "reply": "Xin lỗi, tôi chưa hiểu cử chỉ này."
    },
}


def map_gesture_to_action(gesture_name: str, confidence=None) -> dict:
    key = (gesture_name or "unknown").strip().lower()
    result = GESTURE_TO_ACTION.get(key, GESTURE_TO_ACTION["unknown"]).copy()
    result["confidence"] = confidence
    return result
