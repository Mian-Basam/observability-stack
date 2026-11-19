"""Run register_host.py against a fake Zabbix JSON-RPC API."""
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "register_host.py"


class FakeZabbix(BaseHTTPRequestHandler):
    calls = []
    hosts = {}

    def do_POST(self):  # noqa: N802
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        method, params = req["method"], req["params"]
        FakeZabbix.calls.append((method, self.headers.get("Authorization")))
        names = params.get("filter", {}).get("host", []) if isinstance(params, dict) else []
        result = {
            "user.login": lambda: "tok123",
            "hostgroup.get": lambda: [{"groupid": "2"}],
            "template.get": lambda: [] if names == ["Missing"] else [{"templateid": "10001"}],
            "host.get": lambda: [{"hostid": FakeZabbix.hosts[h]} for h in names if h in FakeZabbix.hosts],
            "host.create": lambda: {"hostids": ["500"]},
            "host.update": lambda: {"hostids": ["500"]},
            "httptest.get": lambda: [],
            "httptest.create": lambda: {"httptestids": ["1"]},
        }[method]()
        if method == "host.create":
            FakeZabbix.hosts[params["host"]] = "500"
        body = json.dumps({"jsonrpc": "2.0", "result": result, "id": req["id"]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    FakeZabbix.calls.clear()
    FakeZabbix.hosts.clear()
    srv = HTTPServer(("127.0.0.1", 0), FakeZabbix)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def run(url, *extra):
    return subprocess.run([sys.executable, str(SCRIPT), "--url", url, *extra],
                          capture_output=True, text=True, timeout=20)


def test_creates_host_and_web_check_then_updates(server):
    r = run(server, "--host", "web01", "--ip", "10.0.0.5", "--web-url", "http://web01/health")
    assert r.returncode == 0, r.stderr
    assert "created host web01 (500)" in r.stdout and "added web scenario" in r.stdout
    # every call after login carries the bearer token
    assert all(auth == "Bearer tok123" for m, auth in FakeZabbix.calls if m != "user.login")

    r = run(server, "--host", "web01", "--ip", "10.0.0.5")
    assert "updated host web01" in r.stdout


def test_missing_template_fails(server):
    r = run(server, "--host", "x", "--ip", "1.1.1.1", "--template", "Missing")
    assert r.returncode != 0 and "template not found" in r.stderr


def test_requires_address(server):
    r = run(server, "--host", "x")
    assert r.returncode != 0 and "give --dns or --ip" in r.stderr
