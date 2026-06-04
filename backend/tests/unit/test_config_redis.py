from app.config import Settings


def test_redis_defaults_disabled(monkeypatch):
    for key in [
        "SECOND_BRAIN_REDIS_ENABLED",
        "SECOND_BRAIN_REDIS_URL",
        "SECOND_BRAIN_RATE_LIMIT_ENABLED",
        "SECOND_BRAIN_CHAT_RATE_LIMIT_REQUESTS",
        "SECOND_BRAIN_INGEST_RATE_LIMIT_REQUESTS",
        "SECOND_BRAIN_SEARCH_CACHE_ENABLED",
        "SECOND_BRAIN_EMBEDDING_CACHE_ENABLED",
    ]:
        monkeypatch.delenv(key, raising=False)

    s = Settings(_env_file=None)
    assert s.redis_enabled is False
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.rate_limit_enabled is True
    assert s.chat_rate_limit_requests == 30
    assert s.ingest_rate_limit_requests == 10
    assert s.search_cache_enabled is True
    assert s.embedding_cache_enabled is True


def test_redis_env_overrides(monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_REDIS_ENABLED", "true")
    monkeypatch.setenv("SECOND_BRAIN_REDIS_URL", "redis://redis:6379/2")
    monkeypatch.setenv("SECOND_BRAIN_CHAT_RATE_LIMIT_REQUESTS", "5")
    monkeypatch.setenv("SECOND_BRAIN_INGEST_RATE_LIMIT_REQUESTS", "2")
    monkeypatch.setenv("SECOND_BRAIN_SEARCH_CACHE_ENABLED", "false")
    monkeypatch.setenv("SECOND_BRAIN_EMBEDDING_CACHE_ENABLED", "false")

    s = Settings(_env_file=None)
    assert s.redis_enabled is True
    assert s.redis_url == "redis://redis:6379/2"
    assert s.chat_rate_limit_requests == 5
    assert s.ingest_rate_limit_requests == 2
    assert s.search_cache_enabled is False
    assert s.embedding_cache_enabled is False
