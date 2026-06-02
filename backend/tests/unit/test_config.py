from app.config import Settings


def test_defaults():
    s = Settings()
    assert s.llm_provider == "gemini"
    assert s.embedding_dim == 384
    assert s.retrieval_top_k == 8


def test_env_override(monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_LLM_PROVIDER", "fake")
    monkeypatch.setenv("SECOND_BRAIN_RETRIEVAL_TOP_K", "3")
    s = Settings()
    assert s.llm_provider == "fake"
    assert s.retrieval_top_k == 3
