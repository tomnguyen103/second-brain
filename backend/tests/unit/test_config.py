from app.config import Settings


def test_defaults(monkeypatch):
    # Clear any env vars the shell may have set, AND disable .env loading, so we test
    # the true code defaults regardless of a developer's local backend/.env (e.g. a
    # leftover SECOND_BRAIN_LLM_PROVIDER=fake from a smoke test). monkeypatch.delenv
    # only clears os.environ; _env_file=None stops pydantic from reading the dotenv file.
    for key in ["SECOND_BRAIN_LLM_PROVIDER", "SECOND_BRAIN_RETRIEVAL_TOP_K",
                "SECOND_BRAIN_RETRIEVAL_MIN_VECTOR_SCORE",
                "SECOND_BRAIN_RETRIEVAL_QUERY_REWRITE_ENABLED",
                "SECOND_BRAIN_GEMINI_API_KEY",
                "SECOND_BRAIN_API_TOKEN",
                "SECOND_BRAIN_RATE_LIMIT_FAIL_CLOSED",
                "SECOND_BRAIN_TRUST_FORWARDED_FOR",
                "SECOND_BRAIN_MCP_ENABLE_MUTATIONS"]:
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)
    assert s.llm_provider == "gemini"
    assert s.embedding_dim == 384
    assert s.retrieval_top_k == 8
    assert s.retrieval_min_vector_score == 0.08
    assert s.retrieval_query_rewrite_enabled is False
    assert s.prompt_version == "rag-v1"
    assert s.mlflow_tracking_uri == "file:./mlruns"
    assert s.api_token is None
    assert s.rate_limit_fail_closed is True
    assert s.trust_forwarded_for is False
    assert s.mcp_enable_mutations is False


def test_env_override(monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_LLM_PROVIDER", "fake")
    monkeypatch.setenv("SECOND_BRAIN_RETRIEVAL_TOP_K", "3")
    monkeypatch.setenv("SECOND_BRAIN_RETRIEVAL_MIN_VECTOR_SCORE", "0.4")
    monkeypatch.setenv("SECOND_BRAIN_RETRIEVAL_QUERY_REWRITE_ENABLED", "true")
    monkeypatch.setenv("SECOND_BRAIN_API_TOKEN", "api-secret")
    monkeypatch.setenv("SECOND_BRAIN_RATE_LIMIT_FAIL_CLOSED", "false")
    monkeypatch.setenv("SECOND_BRAIN_TRUST_FORWARDED_FOR", "true")
    monkeypatch.setenv("SECOND_BRAIN_MCP_ENABLE_MUTATIONS", "true")
    s = Settings()
    assert s.llm_provider == "fake"
    assert s.retrieval_top_k == 3
    assert s.retrieval_min_vector_score == 0.4
    assert s.retrieval_query_rewrite_enabled is True
    assert s.api_token == "api-secret"
    assert s.rate_limit_fail_closed is False
    assert s.trust_forwarded_for is True
    assert s.mcp_enable_mutations is True
