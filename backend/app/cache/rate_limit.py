"""Small fixed-window Redis rate limiter for API endpoints."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import time

from starlette.requests import Request

from app.config import Settings
from app.obs.metrics import RATE_LIMIT_EVENTS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0
    current: int = 0
    limit: int = 0


def client_identity(request: Request) -> str:
    """Best-effort client key for a single-user app behind a reverse proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def check_rate_limit(
    redis_client,
    settings: Settings,
    *,
    bucket: str,
    identity: str,
    limit: int,
    window_seconds: int,
) -> RateLimitDecision:
    """Return a rate-limit decision.

    Redis errors fail open so a cache outage does not take chat or ingest down.
    """
    if (
        not settings.redis_enabled
        or not settings.rate_limit_enabled
        or redis_client is None
        or limit <= 0
        or window_seconds <= 0
    ):
        return RateLimitDecision(allowed=True, limit=limit)

    now = int(time.time())
    window = now // window_seconds
    key = f"rate:{bucket}:{identity}:{window}"
    try:
        current = int(redis_client.incr(key))
        if current == 1:
            redis_client.expire(key, window_seconds)
        if current > limit:
            retry_after = window_seconds - (now % window_seconds)
            RATE_LIMIT_EVENTS.labels(endpoint=bucket, event="limited").inc()
            logger.info("rate limit exceeded", extra={"bucket": bucket, "identity": identity})
            return RateLimitDecision(
                allowed=False,
                retry_after_seconds=max(1, retry_after),
                current=current,
                limit=limit,
            )
        RATE_LIMIT_EVENTS.labels(endpoint=bucket, event="allowed").inc()
        return RateLimitDecision(allowed=True, current=current, limit=limit)
    except Exception as exc:  # noqa: BLE001 - Redis is optional and must fail open
        RATE_LIMIT_EVENTS.labels(endpoint=bucket, event="error").inc()
        logger.warning("Redis rate limit failed open", extra={"bucket": bucket, "error": str(exc)})
        return RateLimitDecision(allowed=True, limit=limit)
