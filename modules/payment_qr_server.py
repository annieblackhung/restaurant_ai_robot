import socket
import threading
import uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


def get_lan_ip():
    """
    Lấy IP LAN để điện thoại cùng Wi-Fi có thể mở trang xác nhận.
    Nếu không lấy được, fallback về 127.0.0.1.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class PaymentQRServer:
    def __init__(self, on_paid_callback, preferred_port=8765):
        self.on_paid_callback = on_paid_callback
        self.host_ip = get_lan_ip()
        self.port = preferred_port
        self.httpd = None
        self.thread = None
        self.payments = {}

    def start(self):
        if self.httpd is not None:
            return

        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                # Không spam terminal.
                return

            def _send_html(self, html, status=200):
                data = html.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                parsed = urlparse(self.path)
                qs = parse_qs(parsed.query)
                pid = qs.get("pid", [""])[0]

                if parsed.path == "/pay":
                    payment = owner.payments.get(pid)
                    if not payment:
                        self._send_html("<h2>Không tìm thấy hóa đơn thanh toán.</h2>", status=404)
                        return

                    amount = payment.get("amount", 0)
                    status = payment.get("status", "pending")

                    html = f"""
                    <!doctype html>
                    <html lang="vi">
                    <head>
                        <meta charset="utf-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1">
                        <title>Thanh toán Robot</title>
                        <style>
                            body {{
                                font-family: Arial, sans-serif;
                                background: #f4f8fb;
                                color: #102a43;
                                text-align: center;
                                padding: 30px;
                            }}
                            .card {{
                                background: white;
                                border-radius: 18px;
                                padding: 24px;
                                max-width: 420px;
                                margin: auto;
                                box-shadow: 0 8px 28px rgba(0,0,0,0.12);
                            }}
                            .amount {{
                                font-size: 28px;
                                font-weight: bold;
                                color: #0f766e;
                                margin: 18px 0;
                            }}
                            button {{
                                border: none;
                                background: #0f766e;
                                color: white;
                                font-size: 18px;
                                font-weight: bold;
                                border-radius: 12px;
                                padding: 14px 22px;
                                width: 100%;
                            }}
                            .muted {{ color: #627d98; font-size: 14px; }}
                        </style>
                    </head>
                    <body>
                        <div class="card">
                            <h2>🤖 Thanh toán hóa đơn</h2>
                            <p>Mã thanh toán:</p>
                            <p><b>{pid}</b></p>
                            <div class="amount">{amount:,} đ</div>
                            <p>Trạng thái hiện tại: <b>{status}</b></p>
                            <form action="/confirm" method="GET">
                                <input type="hidden" name="pid" value="{pid}">
                                <button type="submit">Xác nhận đã thanh toán</button>
                            </form>
                            <p class="muted">Trang này dùng cho demo. Khi bấm xác nhận, GUI sẽ nhận trạng thái đã thanh toán.</p>
                        </div>
                    </body>
                    </html>
                    """
                    self._send_html(html)
                    return

                if parsed.path == "/confirm":
                    payment = owner.payments.get(pid)
                    if not payment:
                        self._send_html("<h2>Không tìm thấy hóa đơn thanh toán.</h2>", status=404)
                        return

                    if payment.get("status") != "paid":
                        payment["status"] = "paid"
                        owner.on_paid_callback(payment)

                    html = """
                    <!doctype html>
                    <html lang="vi">
                    <head>
                        <meta charset="utf-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1">
                        <title>Đã thanh toán</title>
                        <style>
                            body { font-family: Arial, sans-serif; background: #f4f8fb; text-align: center; padding: 30px; color: #102a43; }
                            .card { background: white; border-radius: 18px; padding: 24px; max-width: 420px; margin: auto; box-shadow: 0 8px 28px rgba(0,0,0,0.12); }
                            h1 { color: #0f766e; }
                        </style>
                    </head>
                    <body>
                        <div class="card">
                            <h1>✅ Đã xác nhận thanh toán</h1>
                            <p>Bạn có thể quay lại màn hình demo robot.</p>
                        </div>
                    </body>
                    </html>
                    """
                    self._send_html(html)
                    return

                self._send_html("<h2>Robot Payment Server đang chạy.</h2>")

        last_error = None
        for port in range(self.port, self.port + 40):
            try:
                self.port = port
                self.httpd = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
                break
            except OSError as exc:
                last_error = exc
                self.httpd = None

        if self.httpd is None:
            raise RuntimeError(f"Không mở được payment server: {last_error}")

        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def create_payment(self, amount: int):
        self.start()
        pid = uuid.uuid4().hex[:10].upper()
        url = f"http://{self.host_ip}:{self.port}/pay?pid={pid}"
        payment = {
            "payment_id": pid,
            "amount": amount,
            "status": "pending",
            "url": url,
        }
        self.payments[pid] = payment
        return payment

    def stop(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
