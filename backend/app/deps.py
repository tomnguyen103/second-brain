from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status

from app.config import settings as _settings
from app.db.session import get_db                     # re-exported for routers
from app.embeddings.encoder import Embedder
from app.llm.factory import get_llm_client


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return Embedder()


def get_settings():
    return _settings


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


__all__ = ["get_db", "get_embedder", "get_settings", "get_llm_client", "require_admin"]
