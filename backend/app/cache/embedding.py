"""Optional Redis cache around embedder.encode calls."""
from __future__ import annotations

import hashlib
import json
import logging

from app.config import Settings
from app.obs.metrics import CACHE_EVENTS

logger = logging.getLogger(__name__)


def _embedding_key(embedder, namespace: str, text: str) -> str:
    model = getattr(embedder, "model_name", "unknown")
    dim = getattr(embedder, "dim", "unknown")
    model_hash = hashlib.sha256(f"{model}:{dim}:{namespace}".encode("utf-8")).hexdigest()[:16]
    text_hash = hashlib.sha256((text or "").encode("utf-8")).hexdigest()
    return f"cache:embedding:v1:{model_hash}:{text_hash}"


def _decode_vector(raw: str | bytes | None, dim: int | None) -> list[float] | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, list):
        return None
    vector = [float(v) for v in value]
    if dim is not None and len(vector) != dim:
        return None
    return vector


def encode_with_cache(
    embedder,
    texts: list[str],
    *,
    redis_client,
    settings: Settings,
    namespace: str,
) -> list[list[float]]:
    """Encode texts, reading/writing Redis when enabled.

    Keys store only hashes of the text, never raw note/query text.
    """
    items = list(texts)
    if not items:
        return []
    if not settings.redis_enabled or not settings.embedding_cache_enabled or redis_client is None:
        return embedder.encode(items)

    dim = getattr(embedder, "dim", None)
    results: list[list[float] | None] = [None] * len(items)
    misses: list[tuple[int, str, str]] = []

    try:
        for index, text in enumerate(items):
            key = _embedding_key(embedder, namespace, text)
            vector = _decode_vector(redis_client.get(key), dim)
            if vector is None:
                CACHE_EVENTS.labels(cache="embedding", event="miss").inc()
                misses.append((index, text, key))
            else:
                CACHE_EVENTS.labels(cache="embedding", event="hit").inc()
                results[index] = vector
    except Exception as exc:  # noqa: BLE001 - cache must not block embeddings
        CACHE_EVENTS.labels(cache="embedding", event="error").inc()
        logger.warning("Redis embedding cache read failed", extra={"error": str(exc)})
        return embedder.encode(items)

    if misses:
        encoded = embedder.encode([text for _, text, _ in misses])
        for (index, _text, key), vector in zip(misses, encoded):
            vector = [float(v) for v in vector]
            results[index] = vector
            try:
                redis_client.set(
                    key,
                    json.dumps(vector, separators=(",", ":")),
                    ex=settings.embedding_cache_ttl_seconds,
                )
            except Exception as exc:  # noqa: BLE001 - write-through failure is non-fatal
                CACHE_EVENTS.labels(cache="embedding", event="error").inc()
                logger.warning("Redis embedding cache write failed", extra={"error": str(exc)})

    if any(vector is None for vector in results):
        logger.warning("Redis embedding cache produced incomplete vectors; recomputing batch")
        return embedder.encode(items)
    return [vector for vector in results if vector is not None]
