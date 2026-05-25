ACTION_PRIORITY = {
    "STOP": 100,
    "CALL_STAFF": 90,
    "PAYMENT": 80,
    "PAYMENT_QR": 82,
    "PAID": 85,
    "CONFIRM_ORDER": 75,
    "BRING_WATER": 70,
    "ORDER_FOOD": 60,
    "GREETING": 40,
    "IDLE": 10,
    "UNKNOWN": 0,
}


def get_priority(action: str) -> int:
    return ACTION_PRIORITY.get(action, 0)


def select_highest_priority(events: list) -> dict:
    if not events:
        return {
            "action": "IDLE",
            "reply": "Tôi đang sẵn sàng phục vụ quý khách."
        }
    return max(events, key=lambda event: get_priority(event.get("action", "UNKNOWN")))
