from pathlib import Path

from app.config import Settings


def test_defaults(monkeypatch):
    # Clear any env vars the shell may have set, AND disable .env loading, so we test
    # the true code defaults regardless of a developer's local backend/.env (e.g. a
    # leftover SECOND_BRAIN_LLM_PROVIDER=fake from a smoke test). monkeypatch.delenv
    # only clears os.environ; _env_file=None stops pydantic from reading the dotenv file.
    for key in [
        "SECOND_BRAIN_LLM_PROVIDER",
        "SECOND_BRAIN_RETRIEVAL_TOP_K",
        "SECOND_BRAIN_GEMINI_API_KEY",
        "SECOND_BRAIN_VAULT_PATH",
        "SECOND_BRAIN_VAULT_INDEX_INCLUDE_DIRS",
        "SECOND_BRAIN_VAULT_INDEX_EXCLUDE_DIRS",
        "SECOND_BRAIN_MCP_APPROVAL_TOKEN",
    ]:
        monkeypatch.delenv(key, raising=False)
    s = Settings(_env_file=None)
    assert s.llm_provider == "gemini"
    assert s.embedding_dim == 384
    assert s.retrieval_top_k == 8
    assert s.prompt_version == "rag-v1"
    assert s.mlflow_tracking_uri == "file:./mlruns"
    assert s.vault_path == str(Path.home() / "SecondBrainVault")
    assert s.vault_index_include_dirs == []
    assert s.vault_index_exclude_dirs == [".obsidian", "Templates", "90 Archive"]
    assert s.mcp_approval_token is None


def test_env_override(monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_LLM_PROVIDER", "fake")
    monkeypatch.setenv("SECOND_BRAIN_RETRIEVAL_TOP_K", "3")
    monkeypatch.setenv("SECOND_BRAIN_MCP_APPROVAL_TOKEN", "local-human-ok")
    monkeypatch.setenv("SECOND_BRAIN_VAULT_INDEX_INCLUDE_DIRS", '["10 Research"]')
    monkeypatch.setenv("SECOND_BRAIN_VAULT_INDEX_EXCLUDE_DIRS", '["Templates"]')
    s = Settings()
    assert s.llm_provider == "fake"
    assert s.retrieval_top_k == 3
    assert s.mcp_approval_token == "local-human-ok"
    assert s.vault_index_include_dirs == ["10 Research"]
    assert s.vault_index_exclude_dirs == ["Templates"]
