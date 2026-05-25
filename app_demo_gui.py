import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
from modules.tts_speaker import RobotSpeaker
from modules.ai_controller import RestaurantAIController
from modules.order_manager import MENU_ITEMS
from modules.excel_exporter import (
    FIXED_INVOICE_PATH,
    sync_invoice_excel,
    reset_current_invoice_sheet,
)
from modules.payment_qr_server import PaymentQRServer


class RobotDemoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Restaurant AI Robot Demo - Real Vision + Speech + QR Payment + Excel")
        self.root.geometry("1240x760")
        self.root.minsize(1120, 690)

        self.controller = RestaurantAIController()
        self.menu_vars = {}
        self.quantity_vars = {}
        self.event_logs = []
        self.speaker = RobotSpeaker(lang="vi")
        self.camera_running = False
        self.camera_thread = None
        self.camera_photo = None
        self.last_vision_event_time = 0
        self.vision_interval_sec = 2.0

        self.speech_busy = False

        self.payment_server = PaymentQRServer(self.on_payment_paid_from_qr)
        self.current_payment = None
        self.payment_window = None
        self.qr_photo = None

        # Luồng demo mới:
        # 1) Camera thấy khách -> chỉ chào khách.
        # 2) Khách giơ tay -> robot hỏi khách muốn gọi món gì.
        # 3) Khách chọn/nói món -> hóa đơn cập nhật.
        # 4) Khách like -> xác nhận đơn giống nút "Xác nhận đơn + ghi Excel".
        self.waiting_order_after_gesture = False

        # Gesture chạy ở main thread để tránh lỗi native của MediaPipe/TFLite
        # khi khởi tạo hoặc suy luận trong thread camera.
        self.gesture_ai = None
        self.gesture_trigger = None
        self.gesture_ready = False
        self.gesture_poll_ms = 120
        self.latest_gesture_frame = None
        self.latest_people_for_gesture = []
        self.shared_gesture_result = {
            "gesture": "none",
            "confidence": 0.0,
            "hand_detected": False,
            "reason": "waiting",
        }
        self.last_gesture_debug_at = 0.0

        self._build_layout()
        self.draw_robot("idle")
        self.update_status({
            "reply": f"Xin chào, tôi là robot phục vụ. File Excel cố định: {FIXED_INVOICE_PATH}",
            "robot_expression": "idle",
            "bill_text": "Chưa có món nào.",
            "event": {"action": "IDLE", "source": "system", "intent": "startup"}
        })
        self.sync_excel_safely(payment_status="EMPTY", note="Khởi động demo.")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_layout(self):
        self.root.configure(bg="#F6F8FB")

        # Pack khung phải trước và đặt width cố định để menu/hóa đơn không bị ép hẹp.
        self.left = tk.Frame(self.root, bg="#F6F8FB")
        self.right = tk.Frame(
            self.root,
            bg="#FFFFFF",
            width=380,
            highlightthickness=1,
            highlightbackground="#D9E2EC"
        )
        self.right.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 18), pady=18)
        self.right.pack_propagate(False)
        self.left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=18, pady=18)

        title = tk.Label(
            self.left,
            text="AI Robot Phục Vụ Nhà Hàng",
            font=("Arial", 22, "bold"),
            fg="#243B53",
            bg="#F6F8FB"
        )
        title.pack(anchor="w")

        subtitle = tk.Label(
            self.left,
            text="Demo thật: Camera Vision + Gesture CNN + Speech + Upload Audio + QR Payment + Excel cố định",
            font=("Arial", 12),
            fg="#627D98",
            bg="#F6F8FB"
        )
        subtitle.pack(anchor="w", pady=(0, 12))

        self.canvas = tk.Canvas(
            self.left,
            width=720,
            height=405,
            bg="#EAF4FF",
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.X, pady=8)

        self.reply_var = tk.StringVar()
        self.reply_label = tk.Label(
            self.left,
            textvariable=self.reply_var,
            font=("Arial", 16, "bold"),
            fg="#102A43",
            bg="#F6F8FB",
            wraplength=780,
            justify="left"
        )
        self.reply_label.pack(anchor="w", pady=(8, 4))

        self.action_var = tk.StringVar()
        self.action_label = tk.Label(
            self.left,
            textvariable=self.action_var,
            font=("Consolas", 11),
            fg="#486581",
            bg="#F6F8FB"
        )
        self.action_label.pack(anchor="w")

        real_controls = tk.LabelFrame(
            self.left,
            text="Chức năng thật",
            font=("Arial", 11, "bold"),
            bg="#F6F8FB",
            fg="#243B53",
            padx=10,
            pady=8
        )
        real_controls.pack(fill=tk.X, pady=(14, 0))

        row_real = tk.Frame(real_controls, bg="#F6F8FB")
        row_real.pack(fill=tk.X)

        self.camera_button = self._add_button(row_real, "📷 Bật camera Vision + Gesture", self.toggle_camera, bg="#38B2AC", fg="white")
        self.listen_button = self._add_button(row_real, "🎧 Lắng nghe microphone", self.listen_real_speech, bg="#3182CE", fg="white")
        self.upload_audio_button = self._add_button(row_real, "📁 Upload audio để test", self.upload_audio_file, bg="#805AD5", fg="white")
        self.open_excel_button = self._add_button(row_real, "📊 Cập nhật Excel cố định", lambda: self.sync_excel_safely(note="Cập nhật thủ công từ GUI."), bg="#DD6B20", fg="white")

        demo_controls = tk.LabelFrame(
            self.left,
            text="Nút test nhanh nếu model/camera chưa sẵn sàng",
            font=("Arial", 11, "bold"),
            bg="#F6F8FB",
            fg="#243B53",
            padx=10,
            pady=8
        )
        demo_controls.pack(fill=tk.X, pady=(12, 0))

        row1 = tk.Frame(demo_controls, bg="#F6F8FB")
        row1.pack(fill=tk.X)

        self._add_button(row1, "🎙 Gọi nhân viên", lambda: self.fake_speech("call_staff"))
        self._add_button(row1, "🎙 Gọi nước", lambda: self.fake_speech("order_water"))
        self._add_button(row1, "🎙 Gọi phở", lambda: self.fake_speech("order_pho"))
        self._add_button(row1, "🎙 Gọi bún bò", lambda: self.fake_speech("order_bun_bo"))
        self._add_button(row1, "💳 Thanh toán QR", self.open_payment_qr)

        row2 = tk.Frame(demo_controls, bg="#F6F8FB")
        row2.pack(fill=tk.X, pady=(8, 0))

        self._add_button(row2, "🙋 Giả lập giơ tay", lambda: self.apply_result(self.controller.call_staff()))
        self._add_button(row2, "👍 Xác nhận đơn", self.confirm_order_and_export_excel)
        self._add_button(row2, "👤 Giả lập thấy khách", self.fake_vision_customer)
        self._add_button(row2, "🧹 Xóa hóa đơn", self.clear_bill_and_excel)

        log_frame = tk.LabelFrame(
            self.left,
            text="Log sự kiện",
            font=("Arial", 11, "bold"),
            bg="#F6F8FB",
            fg="#243B53",
            padx=8,
            pady=8
        )
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(14, 0))

        self.log_text = tk.Text(log_frame, height=7, font=("Consolas", 10), bg="#FFFFFF", fg="#243B53")
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Right panel
        right_title = tk.Label(
            self.right,
            text="🍽 MENU",
            font=("Arial", 18, "bold"),
            fg="#102A43",
            bg="#FFFFFF"
        )
        right_title.pack(anchor="w", padx=16, pady=(16, 8))

        menu_frame = tk.Frame(self.right, bg="#FFFFFF")
        menu_frame.pack(fill=tk.X, padx=16)

        for item_id, item in MENU_ITEMS.items():
            row = tk.Frame(menu_frame, bg="#FFFFFF")
            row.pack(fill=tk.X, pady=4)

            var = tk.BooleanVar(value=False)
            qty = tk.IntVar(value=1)

            cb = tk.Checkbutton(
                row,
                text=f'{item["name"]} - {item["price"]:,}đ',
                variable=var,
                bg="#FFFFFF",
                fg="#243B53",
                activebackground="#FFFFFF",
                font=("Arial", 11),
                anchor="w"
            )
            cb.pack(side=tk.LEFT, fill=tk.X, expand=True)

            spin = tk.Spinbox(row, from_=1, to=9, width=3, textvariable=qty, font=("Arial", 10))
            spin.pack(side=tk.RIGHT)

            self.menu_vars[item_id] = var
            self.quantity_vars[item_id] = qty

        add_button = tk.Button(
            self.right,
            text="➕ Thêm món đã tích chọn",
            command=self.add_selected_items,
            bg="#38B2AC",
            fg="white",
            activebackground="#319795",
            relief=tk.FLAT,
            padx=12,
            pady=9,
            font=("Arial", 11, "bold")
        )
        add_button.pack(fill=tk.X, padx=16, pady=(12, 6))

        confirm_button = tk.Button(
            self.right,
            text="👍 Xác nhận đơn + ghi Excel",
            command=self.confirm_order_and_export_excel,
            bg="#3182CE",
            fg="white",
            activebackground="#2B6CB0",
            relief=tk.FLAT,
            padx=12,
            pady=9,
            font=("Arial", 11, "bold")
        )
        confirm_button.pack(fill=tk.X, padx=16, pady=6)

        pay_button = tk.Button(
            self.right,
            text="💳 Thanh toán bằng QR",
            command=self.open_payment_qr,
            bg="#805AD5",
            fg="white",
            activebackground="#6B46C1",
            relief=tk.FLAT,
            padx=12,
            pady=9,
            font=("Arial", 11, "bold")
        )
        pay_button.pack(fill=tk.X, padx=16, pady=6)

        receipt_title = tk.Label(
            self.right,
            text="🧾 HÓA ĐƠN",
            font=("Arial", 16, "bold"),
            fg="#102A43",
            bg="#FFFFFF"
        )
        receipt_title.pack(anchor="w", padx=16, pady=(18, 6))

        self.bill_text = tk.Text(
            self.right,
            width=40,
            height=19,
            font=("Consolas", 10),
            bg="#F8FAFC",
            fg="#243B53",
            relief=tk.FLAT,
            padx=8,
            pady=8
        )
        self.bill_text.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        self.excel_path_var = tk.StringVar(value=f"Excel: {FIXED_INVOICE_PATH}")
        excel_label = tk.Label(
            self.right,
            textvariable=self.excel_path_var,
            bg="#FFFFFF",
            fg="#627D98",
            font=("Arial", 9),
            wraplength=300,
            justify="left"
        )
        excel_label.pack(fill=tk.X, padx=16, pady=(0, 12))

    def _add_button(self, parent, text, command, bg="#FFFFFF", fg="#243B53"):
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground="#EAF4FF",
            relief=tk.FLAT,
            padx=10,
            pady=7,
            font=("Arial", 10, "bold")
        )
        btn.pack(side=tk.LEFT, padx=5)
        return btn

    # =========================
    # Robot face / camera canvas
    # =========================

    def draw_robot(self, expression="idle"):
        if self.camera_running:
            return

        c = self.canvas
        c.delete("all")

        c.create_oval(210, 350, 510, 385, fill="#BFD7EA", outline="")
        self._rounded_rectangle(185, 48, 535, 350, radius=45, fill="#FFFFFF", outline="#9FB3C8", width=4)
        self._rounded_rectangle(150, 155, 188, 245, radius=18, fill="#D9E2EC", outline="#9FB3C8", width=3)
        self._rounded_rectangle(532, 155, 570, 245, radius=18, fill="#D9E2EC", outline="#9FB3C8", width=3)
        c.create_line(360, 48, 360, 20, fill="#627D98", width=4)
        c.create_oval(346, 6, 374, 34, fill="#FFB703", outline="#D97706", width=3)
        self._rounded_rectangle(225, 110, 495, 295, radius=35, fill="#102A43", outline="#334E68", width=3)

        if expression == "happy":
            self._draw_eye(290, 185, "happy")
            self._draw_eye(430, 185, "happy")
            c.create_arc(315, 210, 405, 270, start=200, extent=140, style=tk.ARC, outline="#FFDD57", width=6)
        elif expression == "surprised":
            self._draw_eye(290, 185, "normal")
            self._draw_eye(430, 185, "normal")
            c.create_oval(345, 228, 375, 265, outline="#FFDD57", width=5)
        elif expression == "talk":
            self._draw_eye(290, 185, "normal")
            self._draw_eye(430, 185, "normal")
            self._rounded_rectangle(325, 228, 395, 262, radius=14, fill="#FFDD57", outline="")
        elif expression == "confused":
            c.create_line(265, 175, 315, 160, fill="#7FDBFF", width=7, capstyle=tk.ROUND)
            c.create_line(405, 160, 455, 175, fill="#7FDBFF", width=7, capstyle=tk.ROUND)
            c.create_arc(325, 235, 395, 275, start=20, extent=140, style=tk.ARC, outline="#FFDD57", width=5)
        else:
            self._draw_eye(290, 185, "normal")
            self._draw_eye(430, 185, "normal")
            c.create_line(330, 245, 390, 245, fill="#FFDD57", width=5, capstyle=tk.ROUND)

        c.create_oval(240, 235, 275, 255, fill="#FFB3C1", outline="")
        c.create_oval(445, 235, 480, 255, fill="#FFB3C1", outline="")

    def _draw_eye(self, x, y, mode="normal"):
        c = self.canvas
        if mode == "happy":
            c.create_arc(x-38, y-22, x+38, y+28, start=200, extent=140, style=tk.ARC, outline="#7FDBFF", width=8)
        else:
            c.create_oval(x-35, y-35, x+35, y+35, fill="#7FDBFF", outline="")
            c.create_oval(x-12, y-12, x+12, y+12, fill="#102A43", outline="")
            c.create_oval(x+8, y-16, x+18, y-6, fill="#FFFFFF", outline="")

    def _rounded_rectangle(self, x1, y1, x2, y2, radius=25, **kwargs):
        points = [
            x1+radius, y1, x2-radius, y1, x2, y1, x2, y1+radius,
            x2, y2-radius, x2, y2, x2-radius, y2, x1+radius, y2,
            x1, y2, x1, y2-radius, x1, y1+radius, x1, y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    # =========================
    # Status / Excel
    # =========================

    def apply_result(self, result):
        if not self.camera_running:
            self.draw_robot(result.get("robot_expression", "idle"))
        self.update_status(result)

    def update_status(self, result):
        reply = result.get("reply", "")
        event = result.get("event", {})
        bill = result.get("bill_text", "")

        self.reply_var.set(reply)
        self.speaker.speak(reply)
        self.action_var.set(
            f'Action: {event.get("action", "IDLE")} | Source: {event.get("source", "system")} | Intent: {event.get("intent", "-")}'
        )

        self.bill_text.delete("1.0", tk.END)
        self.bill_text.insert(tk.END, bill)

        log = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": event.get("source", "system"),
            "action": event.get("action", "IDLE"),
            "intent": event.get("intent", "-"),
            "reply": reply,
        }
        self.event_logs.append(log)

        self.log_text.insert(
            tk.END,
            f'[{log["time"]}] [{log["source"]}] {log["action"]}/{log["intent"]} -> {reply}\n'
        )
        self.log_text.see(tk.END)

    def sync_excel_safely(self, payment_status="UNPAID", payment_id="", payment_url="", note="", append_payment=False):
        try:
            saved = sync_invoice_excel(
                self.controller.order_manager,
                self.event_logs,
                payment_status=payment_status,
                payment_id=payment_id,
                payment_url=payment_url,
                note=note,
                append_payment=append_payment,
            )
            self.excel_path_var.set(f"Excel: {saved}")
            return saved
        except Exception as exc:
            messagebox.showerror("Lỗi cập nhật Excel", f"{exc}\n\nNếu thiếu thư viện, chạy:\npip install openpyxl")
            return None

    def make_custom_result(self, reply, source="system", intent="custom", action="IDLE", expression="talk"):
        return {
            "reply": reply,
            "robot_expression": expression,
            "bill_text": self.controller.order_manager.summary_text(),
            "orders": self.controller.order_manager.as_list(),
            "event": {
                "source": source,
                "intent": intent,
                "action": action,
                "reply": reply,
            }
        }

    def handle_vision_result(self, vision_output):
        """
        Luồng vision mới:
        - Camera nhận ra khách -> chỉ chào khách.
        - Không hỏi gọi món ngay, vì câu hỏi gọi món chỉ xuất hiện khi khách giơ tay.
        """
        result = self.controller.process_vision_result(vision_output)
        event = result.get("event", {})

        if event.get("source") == "vision" and event.get("intent") == "customer_detected":
            reply = "Xin chào quý khách."
            result["reply"] = reply
            result["robot_expression"] = "happy"
            result["event"]["reply"] = reply
            result["event"]["action"] = "GREETING"

        return result

    def handle_gesture_event(self, gesture_event):
        """
        Luồng gesture mới:
        - hand_raise: không gọi nhân viên nữa, mà hiểu là khách đang gọi robot để order.
          Robot sẽ hỏi: "Quý khách gọi món gì ạ?"
        - like/thumbs_up: xác nhận đơn giống nút "Xác nhận đơn + ghi Excel".
        - none: không truyền vào đây vì StableGestureTrigger đã bỏ qua.
        """
        gesture = str(gesture_event.get("gesture", "none"))

        if gesture == "hand_raise":
            self.waiting_order_after_gesture = True
            reply = "Quý khách gọi món gì ạ? Quý khách có thể nói lệnh hoặc chọn món ở menu bên phải."
            result = self.make_custom_result(
                reply=reply,
                source="gesture",
                intent="order_request",
                action="WAIT_ORDER",
                expression="talk"
            )
            self.apply_result(result)
            return

        if gesture == "like":
            # Like có tác dụng như nút xác nhận đơn.
            if not self.controller.order_manager.as_list():
                reply = "Hiện chưa có món nào để xác nhận. Quý khách vui lòng chọn món trước."
                result = self.make_custom_result(
                    reply=reply,
                    source="gesture",
                    intent="confirm_empty_order",
                    action="UNKNOWN",
                    expression="confused"
                )
                self.apply_result(result)
                return

            self.confirm_order_and_export_excel()
            return

        # Dự phòng nếu sau này có thêm cử chỉ khác.
        result = self.controller.process_gesture_result(gesture_event)
        self.apply_result(result)

    def log_system_message(self, message):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.insert(tk.END, f"[{now}] [system] {message}\n")
        self.log_text.see(tk.END)

    def confirm_order_and_export_excel(self):
        if not self.controller.order_manager.as_list():
            reply = "Chưa có món nào để xác nhận. Quý khách vui lòng chọn món trước."
            self.apply_result(self.make_custom_result(
                reply=reply,
                source="gui",
                intent="confirm_empty_order",
                action="UNKNOWN",
                expression="confused"
            ))
            return

        result = self.controller.confirm_order()
        result["reply"] = "Dạ, tôi đã xác nhận đơn và cập nhật hóa đơn Excel."
        result["event"]["reply"] = result["reply"]
        self.apply_result(result)
        self.sync_excel_safely(
            payment_status="CONFIRMED_WAITING_PAYMENT",
            note="Tự động xuất Excel sau khi xác nhận đơn."
        )
        self.waiting_order_after_gesture = False

    def clear_bill_and_excel(self):
        result = self.controller.clear_bill()
        self.apply_result(result)
        self.sync_excel_safely(payment_status="EMPTY", note="Xóa hóa đơn thủ công.")

    # =========================
    # QR payment
    # =========================

    def open_payment_qr(self):
        total = self.controller.order_manager.total()
        if total <= 0:
            messagebox.showinfo("Thanh toán", "Chưa có món nào trong hóa đơn.")
            return

        # Trước khi thanh toán, tự xác nhận các món pending để hóa đơn rõ ràng.
        self.controller.order_manager.confirm_pending()

        try:
            payment = self.payment_server.create_payment(total)
        except Exception as exc:
            messagebox.showerror("Lỗi QR Payment Server", str(exc))
            return

        self.current_payment = payment
        payment_id = payment["payment_id"]
        payment_url = payment["url"]

        self.sync_excel_safely(
            payment_status="WAITING_QR_PAYMENT",
            payment_id=payment_id,
            payment_url=payment_url,
            note="Đang chờ khách quét QR và xác nhận thanh toán."
        )

        result = self.controller.payment()
        self.apply_result(result)

        self._show_qr_window(payment)

    def _show_qr_window(self, payment):
        try:
            import qrcode
            from PIL import ImageTk
        except ImportError:
            messagebox.showerror(
                "Thiếu thư viện QR",
                "Cần cài thêm:\npip install qrcode[pil] Pillow"
            )
            return

        if self.payment_window is not None and self.payment_window.winfo_exists():
            self.payment_window.destroy()

        amount = payment["amount"]
        url = payment["url"]

        qr_img = qrcode.make(url)
        qr_img = qr_img.resize((280, 280))
        self.qr_photo = ImageTk.PhotoImage(qr_img)

        win = tk.Toplevel(self.root)
        self.payment_window = win
        win.title("QR thanh toán demo")
        win.geometry("430x560")
        win.configure(bg="#FFFFFF")

        tk.Label(
            win,
            text="Quét QR để thanh toán",
            font=("Arial", 18, "bold"),
            bg="#FFFFFF",
            fg="#102A43"
        ).pack(pady=(18, 4))

        tk.Label(
            win,
            text=f"Số tiền: {amount:,} đ",
            font=("Arial", 15, "bold"),
            bg="#FFFFFF",
            fg="#0F766E"
        ).pack(pady=4)

        tk.Label(win, image=self.qr_photo, bg="#FFFFFF").pack(pady=12)

        tk.Label(
            win,
            text=url,
            font=("Arial", 9),
            bg="#FFFFFF",
            fg="#627D98",
            wraplength=380,
            justify="center"
        ).pack(pady=4)

        tk.Label(
            win,
            text="Điện thoại và laptop nên cùng Wi-Fi.\nSau khi quét, trang web sẽ có nút Xác nhận đã thanh toán.",
            font=("Arial", 10),
            bg="#FFFFFF",
            fg="#486581",
            wraplength=380,
            justify="center"
        ).pack(pady=8)

        # Backup cho lúc demo nếu điện thoại không cùng mạng hoặc QR không mở được.
        tk.Button(
            win,
            text="✅ Xác nhận đã thanh toán trên máy demo",
            command=lambda: self.on_payment_paid_from_qr(payment),
            bg="#0F766E",
            fg="white",
            relief=tk.FLAT,
            padx=12,
            pady=10,
            font=("Arial", 11, "bold")
        ).pack(fill=tk.X, padx=24, pady=(12, 4))

    def on_payment_paid_from_qr(self, payment):
        # Hàm này có thể được gọi từ thread HTTP server, nên đưa về GUI thread.
        self.root.after(0, lambda: self._handle_payment_paid(payment))

    def _handle_payment_paid(self, payment):
        if not self.controller.order_manager.as_list():
            return

        payment_id = payment.get("payment_id", "")
        payment_url = payment.get("url", "")

        # 1. Ghi Excel trạng thái PAID + append lịch sử trước khi reset.
        self.sync_excel_safely(
            payment_status="PAID",
            payment_id=payment_id,
            payment_url=payment_url,
            note="Khách đã xác nhận thanh toán qua QR.",
            append_payment=True
        )

        # 2. Reset hóa đơn trên GUI/controller.
        result = self.controller.mark_paid_and_reset(payment_id=payment_id)
        self.apply_result(result)

        # 3. Cập nhật sheet hóa đơn hiện tại về EMPTY, giữ nguyên lịch sử thanh toán.
        try:
            reset_current_invoice_sheet(
                self.event_logs,
                output_path=FIXED_INVOICE_PATH
            )
        except Exception as exc:
            messagebox.showerror("Lỗi reset Excel", str(exc))

        if self.payment_window is not None and self.payment_window.winfo_exists():
            self.payment_window.destroy()

        messagebox.showinfo(
            "Thanh toán thành công",
            f"Đã thanh toán và reset hóa đơn.\nFile Excel: {FIXED_INVOICE_PATH}"
        )

    # =========================
    # Camera Vision thật
    # =========================

    def toggle_camera(self):
        if self.camera_running:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self):
        if self.camera_running:
            return

        self.camera_running = True
        self.camera_button.config(text="⏹ Tắt camera Vision + Gesture", bg="#E53E3E")
        self.reply_var.set("Đang khởi động camera, Vision AI và Gesture CNN...")

        # Khởi tạo Gesture CNN ở main thread, không khởi tạo trong camera thread.
        # Cách này tránh lỗi native: terminate called without an active exception.
        self.init_gesture_ai_safe()
        self.schedule_gesture_poll()

        self.camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
        self.camera_thread.start()

    def stop_camera(self):
        self.camera_running = False
        self.camera_button.config(text="📷 Bật camera Vision + Gesture", bg="#38B2AC")
        self.camera_photo = None
        self.latest_gesture_frame = None
        self.shared_gesture_result = {
            "gesture": "none",
            "confidence": 0.0,
            "hand_detected": False,
            "reason": "camera_stopped",
        }
        self.draw_robot(self.controller.robot_expression)
        self.reply_var.set("Đã tắt camera Vision + Gesture.")

    def init_gesture_ai_safe(self):
        """
        Khởi tạo Gesture CNN ở main thread.
        Một số máy Ubuntu/MediaPipe có thể crash nếu MediaPipe/TFLite
        được khởi tạo trong thread camera, nên không đặt phần này trong _camera_loop.
        """
        if self.gesture_ready:
            return

        try:
            from modules.gesture_cnn_recognition import CNNGestureRecognizer, StableGestureTrigger

            self.gesture_ai = CNNGestureRecognizer("models/gesture_cnn.pt")
            # Threshold giống file test riêng để dễ demo.
            self.gesture_ai.confidence_threshold = 0.60
            self.gesture_ai.margin_threshold = 0.08
            self.gesture_trigger = StableGestureTrigger(window_size=5, min_hits=2, cooldown_sec=1.5)
            self.gesture_ready = True
            self.log_system_message(
                "Gesture CNN đã sẵn sàng ở main thread. Chỉ nhận cử chỉ của customer; bỏ qua staff."
            )
        except Exception as exc:
            self.gesture_ai = None
            self.gesture_trigger = None
            self.gesture_ready = False
            self.log_system_message(f"Gesture CNN chưa chạy: {exc}")

    def schedule_gesture_poll(self):
        """Lặp gesture inference bằng root.after để chạy ở main thread."""
        if not self.camera_running:
            return
        self.process_gesture_poll()
        self.root.after(self.gesture_poll_ms, self.schedule_gesture_poll)

    def expand_person_bbox_for_gesture(self, bbox, frame_shape, top_ratio=0.75, side_ratio=0.25, bottom_ratio=0.10):
        height, width = frame_shape[:2]
        x1, y1, x2, y2 = [int(v) for v in bbox]
        bw = max(1, x2 - x1)
        bh = max(1, y2 - y1)
        nx1 = max(0, int(x1 - bw * side_ratio))
        nx2 = min(width - 1, int(x2 + bw * side_ratio))
        ny1 = max(0, int(y1 - bh * top_ratio))
        ny2 = min(height - 1, int(y2 + bh * bottom_ratio))
        return [nx1, ny1, nx2, ny2]

    def point_in_bbox_for_gesture(self, point, bbox):
        x, y = point
        x1, y1, x2, y2 = [int(v) for v in bbox]
        return x1 <= x <= x2 and y1 <= y <= y2

    def is_gesture_from_customer_main(self, gesture_result, people, frame_shape):
        """
        Chỉ cho phép gesture nếu tay thuộc customer.
        Nếu tay thuộc staff thì bỏ qua để nhân viên không kích hoạt order/confirm.
        """
        gesture_name = str(gesture_result.get("gesture", "none"))
        if gesture_name in {"none", "unknown"}:
            return True, ""

        customers = [p for p in people if p.get("role") == "customer"]
        staff_members = [p for p in people if p.get("role") == "staff"]

        if not customers:
            return False, "ignored_no_customer"

        hand_bbox = gesture_result.get("hand_bbox")
        if not hand_bbox:
            if staff_members:
                return False, "ignored_no_hand_bbox_with_staff"
            return True, ""

        hx1, hy1, hx2, hy2 = [int(v) for v in hand_bbox]
        hand_center = ((hx1 + hx2) // 2, (hy1 + hy2) // 2)

        customer_hit = False
        for customer in customers:
            cb = customer.get("bbox")
            if not cb:
                continue
            expanded_customer_box = self.expand_person_bbox_for_gesture(cb, frame_shape)
            if self.point_in_bbox_for_gesture(hand_center, expanded_customer_box):
                customer_hit = True
                break

        staff_hit = False
        for staff in staff_members:
            sb = staff.get("bbox")
            if not sb:
                continue
            expanded_staff_box = self.expand_person_bbox_for_gesture(sb, frame_shape)
            if self.point_in_bbox_for_gesture(hand_center, expanded_staff_box):
                staff_hit = True
                break

        if staff_hit and not customer_hit:
            return False, "ignored_staff_gesture"
        if customer_hit:
            return True, ""
        return False, "ignored_hand_not_in_customer_area"

    def process_gesture_poll(self):
        """Chạy gesture inference ở main thread từ frame mới nhất của camera thread."""
        if not self.camera_running or not self.gesture_ready:
            return
        if self.gesture_ai is None or self.gesture_trigger is None:
            return
        if self.latest_gesture_frame is None:
            return

        try:
            frame = self.latest_gesture_frame.copy()
            people = list(self.latest_people_for_gesture or [])

            gesture_result = self.gesture_ai.predict_frame(frame)
            allow_gesture, ignore_reason = self.is_gesture_from_customer_main(
                gesture_result,
                people,
                frame.shape,
            )

            if allow_gesture:
                gesture_for_trigger = gesture_result
            else:
                gesture_for_trigger = {
                    "gesture": "none",
                    "confidence": 0.0,
                    "hand_detected": gesture_result.get("hand_detected", False),
                    "hand_bbox": gesture_result.get("hand_bbox"),
                    "reason": ignore_reason,
                }

            self.shared_gesture_result = gesture_for_trigger
            gesture_event = self.gesture_trigger.update(gesture_for_trigger)
            if gesture_event:
                self.handle_gesture_event(gesture_event)

            # Log debug thưa để biết lý do không kích hoạt.
            now = time.time()
            if now - self.last_gesture_debug_at >= 4.0:
                self.last_gesture_debug_at = now
                reason = gesture_for_trigger.get("reason", "")
                self.log_system_message(
                    f"Gesture debug: {gesture_for_trigger.get('gesture', 'none')} "
                    f"conf={float(gesture_for_trigger.get('confidence', 0.0)):.2f}, "
                    f"hand={gesture_for_trigger.get('hand_detected', False)}, "
                    f"reason={reason or '-'}"
                )
        except Exception as exc:
            self.shared_gesture_result = {
                "gesture": "none",
                "confidence": 0.0,
                "hand_detected": False,
                "reason": f"gesture_error: {exc}",
            }
            self.log_system_message(f"Lỗi gesture poll: {exc}")

    def _camera_loop(self):
        """
        Camera loop đã tối ưu:
        - Lật ngang frame bằng cv2.flip(frame, 1) để không bị ngược trái/phải.
        - Giảm độ phân giải camera về 640x480.
        - Giảm buffer camera để tránh bị trễ hình.
        - Không chạy YOLO/Face/Gesture ở mọi frame để giảm lag.
        """
        try:
            import cv2
            from PIL import Image, ImageTk
            from ultralytics import YOLO
            from modules.face_staff_recognition import StaffFaceRecognizer

            from main_vision import (
                YOLO_MODEL,
                FACE_MODEL,
                CONF_THRESHOLD,
                draw_yolo_objects,
                assign_face_to_persons,
                draw_people_roles,
            )

            # =========================
            # Cấu hình tối ưu tốc độ
            # =========================
            CAMERA_INDEX = 0
            CAMERA_WIDTH = 640
            CAMERA_HEIGHT = 480

            # YOLO + face khá nặng, chỉ chạy mỗi vài frame.
            # Nếu máy yếu, tăng lên 5 hoặc 6. Nếu muốn nhạy hơn, giảm xuống 2 hoặc 3.
            VISION_EVERY_N_FRAMES = 4

            # Gesture chạy mỗi frame để giống file test riêng và nhận cử chỉ nhạy hơn.
            # Nếu máy quá yếu, đổi thành 2.
            GESTURE_EVERY_N_FRAMES = 1

            # Giới hạn số lần update status từ vision để tránh GUI bị spam log.
            self.vision_interval_sec = max(getattr(self, "vision_interval_sec", 2.0), 2.0)

            yolo_model = YOLO(YOLO_MODEL)
            face_ai = StaffFaceRecognizer(encoding_path=FACE_MODEL, tolerance=0.45)

            # Gesture CNN không khởi tạo trong camera thread.
            # Nó được khởi tạo và chạy bằng root.after ở main thread để tránh lỗi native MediaPipe/TFLite.

            cap = cv2.VideoCapture(CAMERA_INDEX)
            if not cap.isOpened():
                raise RuntimeError("Không mở được camera. Thử đổi CAMERA_INDEX từ 0 sang 1 hoặc kiểm tra quyền camera.")

            # Giảm kích thước frame để chạy nhẹ hơn.
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

            # Giảm buffer để hạn chế hiện tượng camera bị trễ.
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

            frame_count = 0
            last_yolo_detections = []
            last_face_results = []
            last_people = []
            last_gesture_result = {"gesture": "none", "confidence": 0.0, "hand_detected": False}

            def draw_cached_yolo_boxes(target_frame, detections):
                """Vẽ lại bbox YOLO đã detect gần nhất trên frame mới để hình mượt hơn."""
                for det in detections:
                    label = det.get("label", "")
                    confidence = float(det.get("confidence", 0.0))
                    x1, y1, x2, y2 = [int(v) for v in det.get("bbox", [0, 0, 0, 0])]
                    color = (255, 0, 0) if label == "person" else (0, 255, 0)
                    cv2.rectangle(target_frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(
                        target_frame,
                        f"{label} {confidence:.2f}",
                        (x1, max(20, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        color,
                        2,
                    )
                return target_frame

            def expand_person_bbox(bbox, frame_shape, top_ratio=0.75, side_ratio=0.25, bottom_ratio=0.10):
                """
                Mở rộng bbox người để bắt được tay giơ cao hơn đầu.
                Nếu không mở rộng, hand_raise có thể nằm ngoài bbox person của YOLO.
                """
                height, width = frame_shape[:2]
                x1, y1, x2, y2 = [int(v) for v in bbox]
                bw = max(1, x2 - x1)
                bh = max(1, y2 - y1)

                nx1 = max(0, int(x1 - bw * side_ratio))
                nx2 = min(width - 1, int(x2 + bw * side_ratio))
                ny1 = max(0, int(y1 - bh * top_ratio))
                ny2 = min(height - 1, int(y2 + bh * bottom_ratio))
                return [nx1, ny1, nx2, ny2]

            def point_in_bbox(point, bbox):
                x, y = point
                x1, y1, x2, y2 = [int(v) for v in bbox]
                return x1 <= x <= x2 and y1 <= y <= y2

            def is_gesture_from_customer(gesture_result, people, frame_shape):
                """
                Chỉ cho phép gesture nếu tay thuộc customer.
                - Nếu không có customer: bỏ qua.
                - Nếu tay nằm trong vùng staff và không nằm trong vùng customer: bỏ qua.
                - Nếu tay nằm trong vùng customer: cho phép.
                """
                gesture_name = str(gesture_result.get("gesture", "none"))
                if gesture_name in {"none", "unknown"}:
                    return True, ""

                customers = [p for p in people if p.get("role") == "customer"]
                staff_members = [p for p in people if p.get("role") == "staff"]

                if not customers:
                    return False, "ignored_no_customer"

                hand_bbox = gesture_result.get("hand_bbox")
                if not hand_bbox:
                    # Gesture thật thường có hand_bbox. Nếu không có bbox thì chỉ cho qua khi không có staff.
                    if staff_members:
                        return False, "ignored_no_hand_bbox_with_staff"
                    return True, ""

                hx1, hy1, hx2, hy2 = [int(v) for v in hand_bbox]
                hand_center = ((hx1 + hx2) // 2, (hy1 + hy2) // 2)

                customer_hit = False
                for customer in customers:
                    cb = customer.get("bbox")
                    if not cb:
                        continue
                    expanded_customer_box = expand_person_bbox(cb, frame_shape)
                    if point_in_bbox(hand_center, expanded_customer_box):
                        customer_hit = True
                        break

                staff_hit = False
                for staff in staff_members:
                    sb = staff.get("bbox")
                    if not sb:
                        continue
                    expanded_staff_box = expand_person_bbox(sb, frame_shape)
                    if point_in_bbox(hand_center, expanded_staff_box):
                        staff_hit = True
                        break

                if staff_hit and not customer_hit:
                    return False, "ignored_staff_gesture"

                if customer_hit:
                    return True, ""

                return False, "ignored_hand_not_in_customer_area"

            while self.camera_running:
                ret, frame = cap.read()
                if not ret:
                    continue

                frame_count += 1

                # Lật ngang để camera giống gương, tránh bị ngược trái/phải.
                frame = cv2.flip(frame, 1)

                # Giữ frame gốc đã lật để gesture xử lý cùng chiều với hình hiển thị.
                raw_frame = frame.copy()

                # =========================
                # Vision AI: YOLO + Face
                # =========================
                if frame_count % VISION_EVERY_N_FRAMES == 0:
                    yolo_results = yolo_model(
                        frame,
                        conf=CONF_THRESHOLD,
                        imgsz=416,
                        verbose=False,
                    )

                    frame, yolo_detections = draw_yolo_objects(frame, yolo_results, yolo_model)
                    face_results = face_ai.recognize(frame)

                    people = assign_face_to_persons(yolo_detections, face_results)

                    last_yolo_detections = yolo_detections
                    last_face_results = face_results
                    last_people = people
                else:
                    yolo_detections = last_yolo_detections
                    face_results = last_face_results
                    people = last_people
                    frame = draw_cached_yolo_boxes(frame, yolo_detections)

                # Vẽ lại face và role từ kết quả gần nhất.
                frame = face_ai.draw(frame, face_results)
                frame = draw_people_roles(frame, people)

                # =========================
                # Gesture CNN overlay
                # =========================
                # Đưa frame + people mới nhất cho gesture poll chạy ở main thread.
                self.latest_gesture_frame = raw_frame.copy()
                self.latest_people_for_gesture = list(people or [])

                gesture_result = getattr(self, "shared_gesture_result", {
                    "gesture": "none",
                    "confidence": 0.0,
                    "hand_detected": False,
                    "reason": "waiting",
                })

                bbox = gesture_result.get("hand_bbox")
                if bbox:
                    gx1, gy1, gx2, gy2 = [int(v) for v in bbox]
                    cv2.rectangle(frame, (gx1, gy1), (gx2, gy2), (255, 180, 0), 2)

                gesture_reason = gesture_result.get("reason", "")
                gesture_text = f"Gesture: {gesture_result.get('gesture', 'none')} {float(gesture_result.get('confidence', 0.0)):.2f}"
                if gesture_reason:
                    gesture_text += f" | {gesture_reason}"
                cv2.putText(frame, gesture_text, (20, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)

                output = {
                    "objects": [obj for obj in yolo_detections if obj.get("label") != "person"],
                    "people": people,
                }

                now = time.time()
                if now - self.last_vision_event_time >= self.vision_interval_sec:
                    self.last_vision_event_time = now
                    result = self.handle_vision_result(output)
                    self.root.after(0, lambda r=result: self.update_status(r))

                # Hiển thị camera lên GUI.
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(frame_rgb)
                image.thumbnail((720, 405))
                photo = ImageTk.PhotoImage(image=image)

                self.root.after(0, lambda p=photo: self._show_camera_photo(p))

            cap.release()

        except Exception as exc:
            self.camera_running = False
            self.root.after(0, lambda: self._camera_error(exc))

    def _show_camera_photo(self, photo):
        if not self.camera_running:
            return
        self.camera_photo = photo
        self.canvas.delete("all")
        self.canvas.create_image(360, 202, image=self.camera_photo, anchor=tk.CENTER)

    def _camera_error(self, exc):
        self.camera_button.config(text="📷 Bật camera Vision + Gesture", bg="#38B2AC")
        self.draw_robot("confused")
        messagebox.showerror("Lỗi camera Vision", str(exc))

    # =========================
    # Speech thật và upload audio
    # =========================

    def listen_real_speech(self):
        if self.speech_busy:
            return

        self.speech_busy = True
        self.listen_button.config(state=tk.DISABLED, text="Đang nghe...")
        self.reply_var.set("Đang nghe lệnh từ microphone...")

        def worker():
            try:
                from modules.speech_ensemble_recognition import SpeechEnsembleRecognizer
                recognizer = SpeechEnsembleRecognizer()
                speech_result = recognizer.listen_and_predict()
                self.root.after(0, lambda: self.handle_speech_result(speech_result))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror(
                    "Lỗi microphone / speech module",
                    f"Không chạy được nhận diện giọng nói thật.\n\n{exc}\n\nBạn vẫn có thể dùng nút Upload audio hoặc nút test nhanh."
                ))
            finally:
                self.root.after(0, self._finish_speech_busy)

        threading.Thread(target=worker, daemon=True).start()

    def upload_audio_file(self):
        if self.speech_busy:
            return

        audio_path = filedialog.askopenfilename(
            title="Chọn file audio để test lệnh",
            filetypes=[
                ("Audio files", "*.wav *.mp3 *.m4a *.flac"),
                ("WAV", "*.wav"),
                ("MP3", "*.mp3"),
                ("All files", "*.*"),
            ]
        )
        if not audio_path:
            return

        self.speech_busy = True
        self.upload_audio_button.config(state=tk.DISABLED, text="Đang xử lý audio...")
        self.reply_var.set(f"Đang nhận diện file audio: {audio_path}")

        def worker():
            try:
                from modules.speech_ensemble_recognition import SpeechEnsembleRecognizer
                recognizer = SpeechEnsembleRecognizer()
                speech_result = recognizer.predict_file(audio_path)
                speech_result["audio_path"] = audio_path
                self.root.after(0, lambda: self.handle_speech_result(speech_result))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror(
                    "Lỗi upload audio / speech module",
                    f"Không nhận diện được file audio.\n\n{exc}"
                ))
            finally:
                self.root.after(0, self._finish_speech_busy)

        threading.Thread(target=worker, daemon=True).start()

    def handle_speech_result(self, speech_result):
        result = self.controller.process_speech_result(speech_result)
        self.apply_result(result)

        intent = result.get("event", {}).get("intent")
        if intent == "payment":
            self.open_payment_qr()

    def _finish_speech_busy(self):
        self.speech_busy = False
        self.listen_button.config(state=tk.NORMAL, text="🎧 Lắng nghe microphone")
        self.upload_audio_button.config(state=tk.NORMAL, text="📁 Upload audio để test")

    # =========================
    # Demo fallback buttons
    # =========================

    def add_selected_items(self):
        added = False
        last_result = None

        for item_id, var in self.menu_vars.items():
            if var.get():
                qty = max(1, int(self.quantity_vars[item_id].get()))
                last_result = self.controller.process_manual_order(item_id, quantity=qty)
                var.set(False)
                self.quantity_vars[item_id].set(1)
                added = True

        if not added:
            messagebox.showinfo("Menu", "Bạn chưa tích chọn món nào.")
            return

        self.apply_result(last_result)

    def fake_speech(self, intent):
        speech_result = {
            "intent": intent,
            "source": "demo_button",
            "cnn_confidence": 0.99
        }
        self.handle_speech_result(speech_result)

    def fake_vision_customer(self):
        result = self.handle_vision_result({
            "people": [
                {
                    "role": "customer",
                    "name": "unknown",
                    "confidence": 0.88,
                    "bbox": [100, 50, 280, 360]
                }
            ],
            "objects": [
                {"label": "table", "confidence": 0.8, "bbox": [20, 200, 400, 350]}
            ]
        })
        self.apply_result(result)

    def on_close(self):
        self.camera_running = False
        try:
            self.payment_server.stop()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    app = RobotDemoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
