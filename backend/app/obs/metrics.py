"""Prometheus metrics for the FastAPI service (Phase 6, ADR-0012).

A dedicated CollectorRegistry (not the process-global default) keeps exposition deterministic
and avoids duplicate-registration errors if the app module is imported more than once (tests,
reload). Requests are labelled by **route template** (e.g. `/data/sources/{source_id}`), not
the raw path, so per-id URLs don't explode the time-series cardinality.
"""
from __future__ import annotations

import time

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

REGISTRY = CollectorRegistry()

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests, by method, route template and status code.",
    ["method", "path", "status"],
    registry=REGISTRY,
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds, by method and route template.",
    ["method", "path"],
    registry=REGISTRY,
)
CACHE_EVENTS = Counter(
    "cache_events_total",
    "Redis-backed cache events by cache name and event.",
    ["cache", "event"],
    registry=REGISTRY,
)
RATE_LIMIT_EVENTS = Counter(
    "rate_limit_events_total",
    "Redis-backed rate-limit decisions by endpoint and event.",
    ["endpoint", "event"],
    registry=REGISTRY,
)

_METRICS_PATH = "/metrics"


def _route_template(request: Request) -> str:
    """The matched route's path template, or 'unmatched' for 404s (bounds cardinality)."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Times each request and records the count + duration metrics, by route template."""

    async def dispatch(self, request: Request, call_next):
        """Record one request's status + latency, then return the response unchanged."""
        # Don't record the scrape endpoint itself — it adds noise and self-reference.
        if request.url.path == _METRICS_PATH:
            return await call_next(request)
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        method = request.method
        path = _route_template(request)
        HTTP_REQUESTS.labels(method=method, path=path, status=str(response.status_code)).inc()
        HTTP_LATENCY.labels(method=method, path=path).observe(elapsed)
        return response


def render() -> tuple[bytes, str]:
    """Return (exposition body, content-type) for the /metrics endpoint."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
