import pytest
from app import create_app, state


@pytest.fixture
def client():
    state.update(error_rate=0.0, latency_ms=0)
    return create_app().test_client()


def test_health_and_metrics(client):
    assert client.get("/health").status_code == 200
    client.get("/api/orders")
    body = client.get("/metrics").data
    assert b"http_requests_total" in body and b"http_request_duration_seconds_bucket" in body


def test_orders_normal(client):
    assert client.get("/api/orders").status_code == 200
    assert client.post("/api/orders").status_code == 201


def test_chaos_errors_full_rate(client):
    client.post("/chaos/errors?rate=1")
    assert client.get("/api/orders").status_code == 500
    client.post("/chaos/reset")
    assert client.get("/api/orders").status_code == 200


def test_chaos_latency(client):
    import time
    client.post("/chaos/latency?ms=200")
    t0 = time.perf_counter()
    client.get("/api/orders")
    assert time.perf_counter() - t0 >= 0.2


@pytest.mark.parametrize("url", ["/chaos/errors?rate=2", "/chaos/latency?ms=-1"])
def test_chaos_validation(client, url):
    assert client.post(url).status_code == 400
