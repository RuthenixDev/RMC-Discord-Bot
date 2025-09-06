import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


def run_healthcheck():
    server = HTTPServer(("0.0.0.0", 8080), Handler)
    print("✅ Healthcheck server started on port 8080")
    server.serve_forever()


def start_in_background():
    """Запускает healthcheck-сервер в отдельном потоке"""
    thread = threading.Thread(target=run_healthcheck, daemon=True)
    thread.start()
