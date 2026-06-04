"""Redis client construction.

Redis is optional: local development defaults it off, and production paths fail open if the
server is temporarily unavailable. Callers still catch operation errors around each use.
"""
from __future__ import annotations

from functools import lru_cache
import logging
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=8)
def _build_client(url: str, timeout_seconds: float):
    try:
        from redis import Redis
    except ImportError:  # pragma: no cover - dependency is installed in supported runtimes
        logger.warning("redis package is not installed; Redis-backed paths disabled")
        return None

    return Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=timeout_seconds,
        socket_timeout=timeout_seconds,
    )


def get_redis_client(settings: Settings) -> Any | None:
    """Return a process-wide Redis client, or None when Redis is disabled."""
    if not settings.redis_enabled:
        return None
    return _build_client(settings.redis_url, settings.redis_socket_timeout_seconds)
