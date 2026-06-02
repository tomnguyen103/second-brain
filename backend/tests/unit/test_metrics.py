"""Prometheus metrics registry + /metrics endpoint (Phase 6, ADR-0012). DB-free."""
from fastapi.testclient import TestClient

from app.obs import metrics


def test_counter_exposition_includes_incremented_series():
    metrics.HTTP_REQUESTS.labels(method="GET", path="/probe", status="200").inc()
    body, content_type = metrics.render()
    text = body.decode()
    assert content_type.startswith("text/plain")
    assert "http_requests_total" in text
    assert 'path="/probe"' in text


def test_metrics_endpoint_exposes_prometheus_text():
    from app.main import app

    with TestClient(app) as c:
        c.get("/openapi.json")  # exercise the middleware against a real (DB-free) route
        r = c.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "http_requests_total" in r.text
    assert "http_request_duration_seconds" in r.text
