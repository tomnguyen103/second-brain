from __future__ import annotations

from fastapi.testclient import TestClient
from starlette.requests import Request

from app import deps
from app.cache.embedding import encode_with_cache
from app.cache.rate_limit import check_rate_limit, client_identity
from app.cache.search import bump_search_cache_epoch, get_search_cache, set_search_cache
from app.chat.service import ChatResult
from app.config import Settings
from app.ingest.service import DocumentResult, IngestResult
from app.main import app
from app.retrieval.fusion import FusedHit
from app.retrieval.hybrid import DisplayChunk


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expirations: dict[str, int] = {}

    def get(self, key: str):
        return self.values.get(key)

    def set(self, key: str, value: str, ex: int | None = None):
        self.values[key] = value
        if ex is not None:
            self.expirations[key] = ex
        return True

    def incr(self, key: str):
        value = int(self.values.get(key) or 0) + 1
        self.values[key] = str(value)
        return value

    def expire(self, key: str, seconds: int):
        self.expirations[key] = seconds
        return True


class FailingRedis(FakeRedis):
    def get(self, key: str):
        raise RuntimeError("redis down")

    def incr(self, key: str):
        raise RuntimeError("redis down")


class CountingEmbedder:
    model_name = "counting"
    dim = 2

    def __init__(self) -> None:
        self.calls = 0

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[float(len(text)), 1.0] for text in texts]


def redis_settings(**overrides) -> Settings:
    return Settings(_env_file=None, redis_enabled=True, **overrides)


def test_rate_limit_allows_then_blocks(monkeypatch):
    from app.cache import rate_limit

    monkeypatch.setattr(rate_limit.time, "time", lambda: 120.0)
    redis = FakeRedis()
    settings = redis_settings(rate_limit_enabled=True)

    first = check_rate_limit(
        redis, settings, bucket="chat", identity="client", limit=1, window_seconds=60
    )
    second = check_rate_limit(
        redis, settings, bucket="chat", identity="client", limit=1, window_seconds=60
    )

    assert first.allowed is True
    assert second.allowed is False
    assert second.retry_after_seconds == 60


def test_rate_limit_fails_closed_when_redis_errors_by_default():
    decision = check_rate_limit(
        FailingRedis(),
        redis_settings(),
        bucket="chat",
        identity="client",
        limit=1,
        window_seconds=60,
    )
    assert decision.allowed is False
    assert decision.retry_after_seconds == 60


def test_rate_limit_can_fail_open_when_explicitly_configured():
    decision = check_rate_limit(
        FailingRedis(),
        redis_settings(rate_limit_fail_closed=False),
        bucket="chat",
        identity="client",
        limit=1,
        window_seconds=60,
    )
    assert decision.allowed is True


def test_client_identity_ignores_spoofable_forwarded_for_by_default():
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/chat",
        "headers": [(b"x-forwarded-for", b"203.0.113.9")],
        "client": ("198.51.100.5", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    })

    assert client_identity(request, Settings(_env_file=None, redis_enabled=False)) == "198.51.100.5"
    assert (
        client_identity(
            request,
            Settings(_env_file=None, redis_enabled=False, trust_forwarded_for=True),
        )
        == "203.0.113.9"
    )


def test_embedding_cache_reuses_vectors_without_raw_text_keys():
    redis = FakeRedis()
    settings = redis_settings()
    embedder = CountingEmbedder()

    first = encode_with_cache(
        embedder, ["alpha"], redis_client=redis, settings=settings, namespace="query"
    )
    second = encode_with_cache(
        embedder, ["alpha"], redis_client=redis, settings=settings, namespace="query"
    )

    assert first == second
    assert embedder.calls == 1
    assert not any("alpha" in key for key in redis.values)


def test_search_cache_hit_and_epoch_invalidation():
    redis = FakeRedis()
    settings = redis_settings()
    payload = {"query": "hnsw", "hits": [], "retrieval": {"method": "hybrid"}}

    assert get_search_cache(
        redis, settings, query="hnsw", top_k=3, source_ids=None, tags=None
    ) is None
    set_search_cache(
        redis,
        settings,
        query="hnsw",
        top_k=3,
        source_ids=None,
        tags=None,
        payload=payload,
    )
    assert get_search_cache(
        redis, settings, query="hnsw", top_k=3, source_ids=None, tags=None
    ) == payload

    bump_search_cache_epoch(redis, settings)
    assert get_search_cache(
        redis, settings, query="hnsw", top_k=3, source_ids=None, tags=None
    ) is None


def _override_app(settings: Settings, redis: FakeRedis):
    app.dependency_overrides[deps.get_db] = lambda: object()
    app.dependency_overrides[deps.get_embedder] = lambda: object()
    app.dependency_overrides[deps.get_settings] = lambda: settings
    app.dependency_overrides[deps.get_redis] = lambda: redis


def test_chat_endpoint_uses_rate_limit(monkeypatch):
    from app.api import chat as chat_api

    settings = redis_settings(llm_provider="fake", chat_rate_limit_requests=1)
    redis = FakeRedis()

    def fake_chat(*args, **kwargs):
        return ChatResult(1, 2, "ok", [], {}, None, 0, {"fused_returned": 0})

    monkeypatch.setattr(chat_api, "chat", fake_chat)
    _override_app(settings, redis)
    try:
        with TestClient(app) as client:
            first = client.post("/chat", json={"message": "hello"})
            second = client.post("/chat", json={"message": "again"})
        assert first.status_code == 200
        assert second.status_code == 429
        assert int(second.headers["retry-after"]) > 0
    finally:
        app.dependency_overrides.clear()


def test_ingest_endpoint_uses_rate_limit(monkeypatch):
    from app.api import ingest as ingest_api

    settings = redis_settings(ingest_rate_limit_requests=1)
    redis = FakeRedis()

    def fake_ingest_documents(*args, **kwargs):
        return IngestResult(
            source_id=1,
            documents=[
                DocumentResult(
                    document_id=2,
                    title="Doc",
                    status="embedded",
                    content_hash="abc",
                    chunk_count=1,
                    embedded_count=1,
                )
            ],
        )

    monkeypatch.setattr(ingest_api, "ingest_documents", fake_ingest_documents)
    _override_app(settings, redis)
    payload = {
        "source": {"type": "manual", "name": "T"},
        "documents": [{"title": "Doc", "content": "hello"}],
    }
    try:
        with TestClient(app) as client:
            first = client.post("/ingest", json=payload)
            second = client.post("/ingest", json=payload)
        assert first.status_code == 200
        assert second.status_code == 429
    finally:
        app.dependency_overrides.clear()


def test_search_endpoint_reuses_cached_response(monkeypatch):
    from app.api import search as search_api

    settings = redis_settings()
    redis = FakeRedis()
    calls = {"hybrid": 0}

    def fake_hybrid_search(*args, **kwargs):
        calls["hybrid"] += 1
        return (
            [FusedHit(chunk_id=10, score=1.0, method="vector", vector_score=0.9, rank=1)],
            {"method": "hybrid", "fused_returned": 1},
        )

    def fake_display_chunks(*args, **kwargs):
        return {
            10: DisplayChunk(
                chunk_id=10,
                content="cached snippet",
                document_id=20,
                document_title="Cached doc",
                source_id=30,
                source_name="Manual",
                char_start=0,
                char_end=14,
            )
        }

    monkeypatch.setattr(search_api, "hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(search_api, "load_display_chunks", fake_display_chunks)
    _override_app(settings, redis)
    try:
        with TestClient(app) as client:
            first = client.get("/search", params={"q": "hnsw", "top_k": 1})
            second = client.get("/search", params={"q": "hnsw", "top_k": 1})
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json() == first.json()
        assert calls["hybrid"] == 1
    finally:
        app.dependency_overrides.clear()
