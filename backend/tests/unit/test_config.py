from app.config import Settings


def test_defaults(monkeypatch):
    # Clear any env vars that the CI shell may have set so we test the true defaults.
    for key in ["SECOND_BRAIN_LLM_PROVIDER", "SECOND_BRAIN_RETRIEVAL_TOP_K",
                "SECOND_BRAIN_GEMINI_API_KEY"]:
        monkeypatch.delenv(key, raising=False)
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
