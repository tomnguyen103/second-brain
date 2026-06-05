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


def client_identity(request: Request, settings: Settings) -> str:
    """Best-effort client key.

    X-Forwarded-For is ignored by default because direct public callers can spoof it. Enable
    SECOND_BRAIN_TRUST_FORWARDED_FOR only when the app is reachable solely through a trusted proxy.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if settings.trust_forwarded_for and forwarded:
        return forwarded.split(",", 1)[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _rate_limit_store_error(
    settings: Settings,
    *,
    bucket: str,
    limit: int,
    window_seconds: int,
) -> RateLimitDecision:
    RATE_LIMIT_EVENTS.labels(endpoint=bucket, event="error").inc()
    if settings.rate_limit_fail_closed:
        logger.error("Redis rate limit failed closed", extra={"bucket": bucket})
        return RateLimitDecision(
            allowed=False,
            retry_after_seconds=max(1, window_seconds),
            limit=limit,
        )
    logger.warning("Redis rate limit failed open", extra={"bucket": bucket})
    return RateLimitDecision(allowed=True, limit=limit)


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

    Redis errors fail closed by default when Redis is enabled, because silently removing
    protection on public mutation/chat endpoints is riskier than a temporary 429 for this
    single-user app. Operators can set SECOND_BRAIN_RATE_LIMIT_FAIL_CLOSED=false if they
    deliberately prefer availability during an outage.
    """
    if not settings.rate_limit_enabled or limit <= 0 or window_seconds <= 0:
        return RateLimitDecision(allowed=True, limit=limit)
    if not settings.redis_enabled:
        return RateLimitDecision(allowed=True, limit=limit)
    if redis_client is None:
        return _rate_limit_store_error(
            settings, bucket=bucket, limit=limit, window_seconds=window_seconds
        )

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
    except Exception as exc:  # noqa: BLE001 - Redis errors map to a configured security posture
        logger.warning("Redis rate limit operation failed", extra={"bucket": bucket, "error": str(exc)})
        return _rate_limit_store_error(
            settings, bucket=bucket, limit=limit, window_seconds=window_seconds
        )
