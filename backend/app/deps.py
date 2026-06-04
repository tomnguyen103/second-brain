from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status

from app.config import settings as _settings
from app.cache.redis_client import get_redis_client
from app.db.session import get_db                     # re-exported for routers
from app.llm.factory import get_llm_client


@lru_cache(maxsize=1)
def get_embedder():
    """Return the process-wide embedder singleton for the configured provider (ADR-0002).

    `local` loads sentence-transformers/torch on first use; `gemini` calls the hosted API
    (no torch — keeps the box small). Selected by `settings.embedding_provider`.
    """
    from app.embeddings.factory import build_embedder
    return build_embedder(_settings)


def get_settings():
    """Return the application settings (overridable in tests via dependency_overrides)."""
    return _settings


def get_redis(settings=Depends(get_settings)):
    """Return the optional Redis client, or None when Redis is disabled."""
    return get_redis_client(settings)


def require_admin(
    authorization: str | None = Header(default=None),
    settings=Depends(get_settings),
) -> bool:
    """Guard for destructive/admin endpoints (Phase 6, ADR-0012).

    503 when no admin token is configured (the feature is off by default — a single-user app
    with no token shouldn't expose delete/export); 401 when the Bearer token is missing/wrong.
    """
    if not settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin endpoints are disabled (set SECOND_BRAIN_ADMIN_TOKEN to enable)",
        )
    if authorization != f"Bearer {settings.admin_token}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing admin token",
        )
    return True


__all__ = [
    "get_db",
    "get_embedder",
    "get_settings",
    "get_redis",
    "get_llm_client",
    "require_admin",
]
