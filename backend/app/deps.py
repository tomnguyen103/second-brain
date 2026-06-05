from functools import lru_cache
import secrets

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
    x_second_brain_admin_token: str | None = Header(
        default=None, alias="X-Second-Brain-Admin-Token"
    ),
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
    token = (x_second_brain_admin_token or "").strip()
    if not token or not secrets.compare_digest(token, settings.admin_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing admin token",
        )
    return True


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def require_api_access(
    authorization: str | None = Header(default=None),
    settings=Depends(get_settings),
) -> bool:
    """Guard personal-data API endpoints with a single-user bearer token.

    Local development remains keyless unless SECOND_BRAIN_API_TOKEN is set. Production compose
    requires it so public /api routes cannot read or mutate notes, conversations, sources,
    feedback, tasks, or research jobs without an operator-provided token.
    """
    if not settings.api_token:
        return True

    token = _bearer_token(authorization)
    if token is None or not secrets.compare_digest(token, settings.api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing API token",
        )
    return True


__all__ = [
    "get_db",
    "get_embedder",
    "get_settings",
    "get_redis",
    "get_llm_client",
    "require_admin",
    "require_api_access",
]
