"""Minimal Alertmanager webhook receiver.

Prints each alert as one readable line and keeps the last 100 in memory
(GET /alerts), so alert routing can be verified without Slack or email.
"""
import json
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RECEIVED = deque(maxlen=100)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        receiver = self.path.strip("/") or "default"
        for alert in payload.get("alerts", []):
            item = {
                "received_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "receiver": receiver,
                "status": alert.get("status"),
                "alertname": alert.get("labels", {}).get("alertname"),
                "severity": alert.get("labels", {}).get("severity"),
                "summary": alert.get("annotations", {}).get("summary"),
            }
            RECEIVED.append(item)
            print(f"[{item['receiver']}] {item['status'].upper():8} {item['severity'] or '-':8} "
                  f"{item['alertname']}: {item['summary']}", flush=True)
        self.send_response(200)
        self.end_headers()

    def do_GET(self):  # noqa: N802
        body = json.dumps(list(RECEIVED), indent=2).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print("webhook-logger listening on :9095", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 9095), Handler).serve_forever()
