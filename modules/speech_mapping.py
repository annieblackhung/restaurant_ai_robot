# modules/speech_mapping.py


SPEECH_INTENT_TO_ACTION = {
    "call_staff": {
        "source": "speech",
        "intent": "call_staff",
        "action": "CALL_STAFF",
        "reply": "Dạ, tôi sẽ gọi nhân viên hỗ trợ quý khách."
    },

    "order_water": {
        "source": "speech",
        "intent": "order_water",
        "action": "BRING_WATER",
        "reply": "Dạ, tôi sẽ mang nước đến cho quý khách."
    },

    "order_pho": {
        "source": "speech",
        "intent": "order_pho",
        "action": "ORDER_FOOD",
        "item": "pho",
        "reply": "Dạ, tôi đã ghi nhận món phở."
    },

    "order_bun_bo": {
        "source": "speech",
        "intent": "order_bun_bo",
        "action": "ORDER_FOOD",
        "item": "bun_bo",
        "reply": "Dạ, tôi đã ghi nhận món bún bò."
    },

    "payment": {
        "source": "speech",
        "intent": "payment",
        "action": "PAYMENT",
        "reply": "Dạ, tôi sẽ hỗ trợ thanh toán cho quý khách."
    },

    "unknown": {
        "source": "speech",
        "intent": "unknown",
        "action": "UNKNOWN",
        "reply": "Xin lỗi, tôi chưa hiểu yêu cầu."
    }
}


def map_speech_intent(intent, confidence=None):
    result = SPEECH_INTENT_TO_ACTION.get(
        intent,
        SPEECH_INTENT_TO_ACTION["unknown"]
    ).copy()

    result["confidence"] = confidence

    return result
