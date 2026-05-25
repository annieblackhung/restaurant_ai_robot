from typing import Dict, Any

from modules.action_priority import select_highest_priority
from modules.gesture_mapping import map_gesture_to_action
from modules.order_manager import OrderManager, MENU_ITEMS

try:
    from modules.speech_mapping import map_speech_intent
except Exception:
    def map_speech_intent(intent, confidence=None):
        mapping = {
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
            },
        }
        result = mapping.get(intent, mapping["unknown"]).copy()
        result["confidence"] = confidence
        return result


class RestaurantAIController:
    # Chỉ giữ 3 intent gọi món chính.
    SPEECH_INTENT_TO_ITEM = {
        "order_pho": "pho",
        "order_bun_bo": "bun_bo",
        "order_water": "water",
    }

    def __init__(self):
        self.order_manager = OrderManager()
        self.last_reply = "Xin chào, tôi có thể giúp gì cho quý khách?"
        self.robot_expression = "idle"
        self.last_customer_seen = False

    def _build_response(self, event: dict) -> dict:
        action = event.get("action", "IDLE")
        reply = event.get("reply", "Tôi đang sẵn sàng phục vụ quý khách.")

        if action in ["ORDER_FOOD", "BRING_WATER", "CONFIRM_ORDER", "PAID"]:
            expression = "happy"
        elif action == "CALL_STAFF":
            expression = "surprised"
        elif action in ["PAYMENT", "PAYMENT_QR"]:
            expression = "talk"
        elif action == "UNKNOWN":
            expression = "confused"
        else:
            expression = "idle"

        self.last_reply = reply
        self.robot_expression = expression

        return {
            "action": action,
            "reply": reply,
            "robot_expression": expression,
            "orders": self.order_manager.as_list(),
            "bill_text": self.order_manager.summary_text(),
            "event": event
        }

    def process_speech_result(self, speech_result: Dict[str, Any]) -> dict:
        intent = speech_result.get("intent") or speech_result.get("final_class") or "unknown"
        confidence = speech_result.get("cnn_confidence") or speech_result.get("confidence")

        event = map_speech_intent(intent, confidence=confidence)
        event["raw"] = speech_result

        item_id = event.get("item") or self.SPEECH_INTENT_TO_ITEM.get(intent)

        if item_id:
            try:
                self.order_manager.add_item(item_id)
                if intent == "order_water":
                    event["action"] = "BRING_WATER"
                else:
                    event["action"] = "ORDER_FOOD"
                event["reply"] = MENU_ITEMS[item_id]["reply"]
                event["item"] = item_id
            except ValueError:
                event["action"] = "UNKNOWN"
                event["reply"] = "Xin lỗi, món này chưa có trong menu."

        if intent == "payment":
            total = self.order_manager.total()
            event["bill"] = self.order_manager.as_list()
            event["total"] = total
            event["action"] = "PAYMENT"
            event["reply"] = f"Dạ, tổng hóa đơn hiện tại là {total:,} đồng. Vui lòng quét mã QR để thanh toán."

        return self._build_response(event)

    def process_gesture_result(self, gesture_result: Dict[str, Any]) -> dict:
        gesture_name = (
            gesture_result.get("gesture")
            or gesture_result.get("class")
            or gesture_result.get("name")
            or "unknown"
        )
        confidence = gesture_result.get("confidence")

        event = map_gesture_to_action(gesture_name, confidence=confidence)
        event["raw"] = gesture_result

        if event["action"] == "CONFIRM_ORDER":
            count = self.order_manager.confirm_pending()
            if count > 0:
                event["reply"] = f"Dạ, tôi đã xác nhận {count} món trong đơn và đã cập nhật file Excel."
            else:
                event["reply"] = "Hiện chưa có món nào cần xác nhận."

        return self._build_response(event)

    def process_vision_result(self, vision_result: Dict[str, Any]) -> dict:
        people = vision_result.get("people", [])
        customers = [p for p in people if p.get("role") == "customer"]

        if customers and not self.last_customer_seen:
            self.last_customer_seen = True
            event = {
                "source": "vision",
                "intent": "customer_detected",
                "action": "GREETING",
                "reply": "Xin chào quý khách, quý khách muốn dùng món gì ạ?",
                "raw": vision_result,
            }
        elif not customers:
            self.last_customer_seen = False
            event = {
                "source": "vision",
                "intent": "no_customer",
                "action": "IDLE",
                "reply": "Tôi đang quan sát khu vực phục vụ.",
                "raw": vision_result,
            }
        else:
            event = {
                "source": "vision",
                "intent": "customer_tracking",
                "action": "IDLE",
                "reply": self.last_reply,
                "raw": vision_result,
            }

        return self._build_response(event)

    def process_manual_order(self, item_id: str, quantity: int = 1) -> dict:
        try:
            item = self.order_manager.add_item(item_id, quantity=quantity)
            event = {
                "source": "gui",
                "intent": "manual_order",
                "action": "ORDER_FOOD" if item_id != "water" else "BRING_WATER",
                "item": item_id,
                "reply": f"Dạ, tôi đã thêm {item.name} x{quantity} vào hóa đơn."
            }
        except ValueError:
            event = {
                "source": "gui",
                "intent": "manual_order",
                "action": "UNKNOWN",
                "reply": "Món này chưa có trong menu."
            }

        return self._build_response(event)

    def process_multiple_events(self, events: list) -> dict:
        chosen = select_highest_priority(events)
        return self._build_response(chosen)

    def confirm_order(self) -> dict:
        return self.process_gesture_result({"gesture": "like", "confidence": 1.0})

    def call_staff(self) -> dict:
        return self.process_gesture_result({"gesture": "hand_raise", "confidence": 1.0})

    def payment(self) -> dict:
        return self.process_speech_result({"intent": "payment", "confidence": 1.0})

    def mark_paid_and_reset(self, payment_id: str = "") -> dict:
        paid_total = self.order_manager.total()
        self.order_manager.clear()
        event = {
            "source": "payment_qr",
            "intent": "payment_confirmed",
            "action": "PAID",
            "payment_id": payment_id,
            "reply": f"Thanh toán thành công {paid_total:,} đồng. Hóa đơn đã được cập nhật Excel và đã reset."
        }
        return self._build_response(event)

    def clear_bill(self) -> dict:
        self.order_manager.clear()
        event = {
            "source": "gui",
            "intent": "clear_bill",
            "action": "IDLE",
            "reply": "Dạ, tôi đã xóa hóa đơn demo."
        }
        return self._build_response(event)
