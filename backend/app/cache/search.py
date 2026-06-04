"""Optional Redis cache for hot GET /search responses."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from app.config import Settings
from app.obs.metrics import CACHE_EVENTS

logger = logging.getLogger(__name__)

_SEARCH_EPOCH_KEY = "cache:search:epoch"


def _json_key(data: dict[str, Any]) -> str:
    body = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _search_epoch(redis_client) -> str:
    value = redis_client.get(_SEARCH_EPOCH_KEY)
    return str(value or "0")


def search_cache_key(
    redis_client,
    settings: Settings,
    *,
    query: str,
    top_k: int,
    source_ids: list[int] | None,
    tags: list[str] | None,
) -> str:
    epoch = _search_epoch(redis_client)
    payload = {
        "epoch": epoch,
        "query": query,
        "top_k": top_k,
        "source_ids": sorted(source_ids or []),
        "tags": sorted(tags or []),
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "gemini_embedding_model": settings.gemini_embedding_model,
        "retrieval": {
            "k_vector": settings.retrieval_k_vector,
            "k_fulltext": settings.retrieval_k_fulltext,
            "rrf_k": settings.retrieval_rrf_k,
            "w_vector": settings.retrieval_w_vector,
            "w_fulltext": settings.retrieval_w_fulltext,
            "min_vector_score": settings.retrieval_min_vector_score,
        },
    }
    return f"cache:search:v1:{_json_key(payload)}"


def get_search_cache(
    redis_client,
    settings: Settings,
    *,
    query: str,
    top_k: int,
    source_ids: list[int] | None,
    tags: list[str] | None,
) -> dict | None:
    if not settings.redis_enabled or not settings.search_cache_enabled or redis_client is None:
        return None
    try:
        key = search_cache_key(
            redis_client, settings, query=query, top_k=top_k, source_ids=source_ids, tags=tags
        )
        raw = redis_client.get(key)
        if raw is None:
            CACHE_EVENTS.labels(cache="search", event="miss").inc()
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        CACHE_EVENTS.labels(cache="search", event="hit").inc()
        return json.loads(raw)
    except Exception as exc:  # noqa: BLE001 - cache errors fail open
        CACHE_EVENTS.labels(cache="search", event="error").inc()
        logger.warning("Redis search cache read failed", extra={"error": str(exc)})
        return None


def set_search_cache(
    redis_client,
    settings: Settings,
    *,
    query: str,
    top_k: int,
    source_ids: list[int] | None,
    tags: list[str] | None,
    payload: dict,
) -> None:
    if not settings.redis_enabled or not settings.search_cache_enabled or redis_client is None:
        return
    try:
        key = search_cache_key(
            redis_client, settings, query=query, top_k=top_k, source_ids=source_ids, tags=tags
        )
        redis_client.set(
            key,
            json.dumps(payload, separators=(",", ":"), sort_keys=True),
            ex=settings.search_cache_ttl_seconds,
        )
    except Exception as exc:  # noqa: BLE001 - cache writes are best effort
        CACHE_EVENTS.labels(cache="search", event="error").inc()
        logger.warning("Redis search cache write failed", extra={"error": str(exc)})


def bump_search_cache_epoch(redis_client, settings: Settings) -> None:
    """Invalidate hot search results after new content is embedded."""
    if not settings.redis_enabled or not settings.search_cache_enabled or redis_client is None:
        return
    try:
        redis_client.incr(_SEARCH_EPOCH_KEY)
    except Exception as exc:  # noqa: BLE001 - stale cache expires by TTL even if bump fails
        CACHE_EVENTS.labels(cache="search", event="error").inc()
        logger.warning("Redis search cache invalidation failed", extra={"error": str(exc)})
