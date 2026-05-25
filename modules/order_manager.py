from dataclasses import dataclass, asdict
from typing import Dict, List
import time


# Menu demo rút gọn theo yêu cầu: chỉ giữ các món/chức năng chính.
MENU_ITEMS: Dict[str, dict] = {
    "pho": {
        "name": "Phở bò",
        "price": 45000,
        "intent": "order_pho",
        "reply": "Dạ, tôi đã ghi nhận món phở bò."
    },
    "bun_bo": {
        "name": "Bún bò",
        "price": 50000,
        "intent": "order_bun_bo",
        "reply": "Dạ, tôi đã ghi nhận món bún bò."
    },
    "water": {
        "name": "Chai nước",
        "price": 10000,
        "intent": "order_water",
        "reply": "Dạ, tôi sẽ mang nước đến cho quý khách."
    },
}


@dataclass
class OrderItem:
    item_id: str
    name: str
    price: int
    quantity: int = 1
    status: str = "pending"
    created_at: float = 0.0

    def to_dict(self) -> dict:
        data = asdict(self)
        data["subtotal"] = self.price * self.quantity
        return data


class OrderManager:
    def __init__(self):
        self.items: List[OrderItem] = []

    def add_item(self, item_id: str, quantity: int = 1) -> OrderItem:
        if item_id not in MENU_ITEMS:
            raise ValueError(f"Món không tồn tại trong menu: {item_id}")

        menu_item = MENU_ITEMS[item_id]

        # Gộp món cùng loại nếu vẫn đang chờ xác nhận.
        for item in self.items:
            if item.item_id == item_id and item.status == "pending":
                item.quantity += quantity
                return item

        order_item = OrderItem(
            item_id=item_id,
            name=menu_item["name"],
            price=menu_item["price"],
            quantity=quantity,
            status="pending",
            created_at=time.time()
        )
        self.items.append(order_item)
        return order_item

    def confirm_pending(self) -> int:
        count = 0
        for item in self.items:
            if item.status == "pending":
                item.status = "confirmed"
                count += 1
        return count

    def cancel_pending(self) -> int:
        before = len(self.items)
        self.items = [item for item in self.items if item.status != "pending"]
        return before - len(self.items)

    def clear(self) -> None:
        self.items.clear()

    def total(self) -> int:
        return sum(item.price * item.quantity for item in self.items)

    def pending_total(self) -> int:
        return sum(item.price * item.quantity for item in self.items if item.status == "pending")

    def confirmed_total(self) -> int:
        return sum(item.price * item.quantity for item in self.items if item.status == "confirmed")

    def as_list(self) -> List[dict]:
        return [item.to_dict() for item in self.items]

    def summary_text(self) -> str:
        if not self.items:
            return "Chưa có món nào."

        lines = []
        for idx, item in enumerate(self.items, start=1):
            status = "chờ xác nhận" if item.status == "pending" else "đã xác nhận"
            subtotal = item.price * item.quantity
            lines.append(
                f"{idx}. {item.name} x{item.quantity} - {subtotal:,}đ ({status})"
            )

        lines.append("-" * 42)
        lines.append(f"Tạm tính: {self.total():,}đ")
        lines.append(f"Đã xác nhận: {self.confirmed_total():,}đ")
        lines.append(f"Chờ xác nhận: {self.pending_total():,}đ")
        return "\n".join(lines)
