"""Demo 'orders' service that produces realistic metrics and logs.

Chaos endpoints let you trigger the conditions the alerts watch for:
  POST /chaos/errors?rate=0.5      -> 50% of /api/orders return 500
  POST /chaos/latency?ms=800       -> add 800ms to every request
  POST /chaos/reset                -> back to normal
"""
import json
import logging
import os
import random
import threading
import time

from flask import Flask, g, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

SERVICE = os.getenv("SERVICE_NAME", "orders")

REQUESTS = Counter("http_requests_total", "HTTP requests", ["service", "method", "route", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["service", "route"],
                    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))
IN_FLIGHT = Gauge("http_requests_in_flight", "In-flight requests", ["service"])
ORDERS = Counter("orders_created_total", "Orders created", ["service"])
QUEUE_DEPTH = Gauge("orders_queue_depth", "Simulated backlog of unprocessed orders", ["service"])
CHAOS = Gauge("chaos_enabled", "1 when a chaos mode is active", ["service", "mode"])

state = {"error_rate": 0.0, "latency_ms": 0}
lock = threading.Lock()


class JsonFormatter(logging.Formatter):
    def format(self, record):
        base = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname,
                "service": SERVICE, "msg": record.getMessage()}
        base.update(getattr(record, "fields", {}))
        return json.dumps(base)


log = logging.getLogger(SERVICE)
_h = logging.StreamHandler()
_h.setFormatter(JsonFormatter())
log.handlers = [_h]
log.setLevel(logging.INFO)
log.propagate = False


def create_app():
    app = Flask(__name__)

    @app.before_request
    def _before():
        g.t0 = time.perf_counter()
        IN_FLIGHT.labels(SERVICE).inc()
        with lock:
            extra = state["latency_ms"]
        if extra and request.path.startswith("/api/"):
            time.sleep(extra / 1000)

    @app.after_request
    def _after(resp):
        route = request.url_rule.rule if request.url_rule else "unmatched"
        IN_FLIGHT.labels(SERVICE).dec()
        if route != "/metrics":
            elapsed = time.perf_counter() - g.t0
            REQUESTS.labels(SERVICE, request.method, route, resp.status_code).inc()
            LATENCY.labels(SERVICE, route).observe(elapsed)
            level = logging.ERROR if resp.status_code >= 500 else logging.INFO
            log.log(level, "request", extra={"fields": {
                "method": request.method, "route": route, "status": resp.status_code,
                "duration_ms": round(elapsed * 1000, 1)}})
        return resp

    @app.get("/health")
    def health():
        return jsonify(status="ok", service=SERVICE)

    @app.get("/metrics")
    def metrics():
        return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

    @app.get("/api/orders")
    def list_orders():
        with lock:
            rate = state["error_rate"]
        if random.random() < rate:
            return jsonify(error="upstream payment gateway timeout"), 500
        return jsonify(orders=[{"id": i, "amount": round(random.uniform(5, 500), 2)} for i in range(5)])

    @app.post("/api/orders")
    def create_order():
        with lock:
            rate = state["error_rate"]
        if random.random() < rate:
            return jsonify(error="database write failed"), 500
        ORDERS.labels(SERVICE).inc()
        QUEUE_DEPTH.labels(SERVICE).set(random.randint(0, 20))
        return jsonify(id=random.randint(1000, 9999), status="created"), 201

    @app.post("/chaos/errors")
    def chaos_errors():
        rate = float(request.args.get("rate", 0.5))
        if not 0 <= rate <= 1:
            return jsonify(error="rate must be between 0 and 1"), 400
        with lock:
            state["error_rate"] = rate
        CHAOS.labels(SERVICE, "errors").set(1 if rate else 0)
        log.warning("chaos: error rate set", extra={"fields": {"error_rate": rate}})
        return jsonify(state)

    @app.post("/chaos/latency")
    def chaos_latency():
        ms = int(request.args.get("ms", 800))
        if not 0 <= ms <= 10000:
            return jsonify(error="ms must be between 0 and 10000"), 400
        with lock:
            state["latency_ms"] = ms
        CHAOS.labels(SERVICE, "latency").set(1 if ms else 0)
        log.warning("chaos: latency set", extra={"fields": {"latency_ms": ms}})
        return jsonify(state)

    @app.post("/chaos/reset")
    def chaos_reset():
        with lock:
            state.update(error_rate=0.0, latency_ms=0)
        CHAOS.labels(SERVICE, "errors").set(0)
        CHAOS.labels(SERVICE, "latency").set(0)
        return jsonify(state)

    return app


app = create_app()
