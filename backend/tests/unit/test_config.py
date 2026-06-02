from app.config import Settings


def test_defaults(monkeypatch):
    # Clear any env vars the shell may have set, AND disable .env loading, so we test
    # the true code defaults regardless of a developer's local backend/.env (e.g. a
    # leftover SECOND_BRAIN_LLM_PROVIDER=fake from a smoke test). monkeypatch.delenv
    # only clears os.environ; _env_file=None stops pydantic from reading the dotenv file.
    for key in ["SECOND_BRAIN_LLM_PROVIDER", "SECOND_BRAIN_RETRIEVAL_TOP_K",
                "SECOND_BRAIN_GEMINI_API_KEY"]:
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)
    assert s.llm_provider == "gemini"
    assert s.embedding_dim == 384
    assert s.retrieval_top_k == 8


def test_env_override(monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_LLM_PROVIDER", "fake")
    monkeypatch.setenv("SECOND_BRAIN_RETRIEVAL_TOP_K", "3")
    s = Settings()
    assert s.llm_provider == "fake"
    assert s.retrieval_top_k == 3
