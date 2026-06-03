"""Application settings."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from `SECOND_BRAIN_*` env vars and an optional `.env` file."""

    model_config = SettingsConfigDict(
        env_prefix="SECOND_BRAIN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # psycopg3 driver URL. Override via SECOND_BRAIN_DATABASE_URL.
    # Host port 5433: Docker DB published on 5433 to avoid clash with native PG on 5432.
    database_url: str = "postgresql+psycopg://second_brain:second_brain@localhost:5433/second_brain"

    # LLM driver (ADR-0001, ADR-0007)
    llm_provider: str = "gemini"          # gemini | ollama | fake
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # Embeddings (ADR-0002). Provider: `local` (sentence-transformers/torch, runs on the box) or
    # `gemini` (hosted API — drops the ~2 GB torch RAM footprint so the stack fits a small VPS).
    embedding_provider: str = "local"     # local | gemini
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    # Used when embedding_provider=gemini; requested at output_dimensionality=embedding_dim (384)
    # so it drops into the existing vector(384) schema with no migration.
    gemini_embedding_model: str = "gemini-embedding-001"

    # Chunking (ADR-0003)
    chunk_target_tokens: int = 512
    chunk_overlap_ratio: float = 0.15

    # Retrieval (ADR-0005)
    retrieval_k_vector: int = 20
    retrieval_k_fulltext: int = 20
    retrieval_rrf_k: int = 60
    retrieval_top_k: int = 8
    retrieval_w_vector: float = 1.0
    retrieval_w_fulltext: float = 1.0

    # Chat (ADR-0006)
    history_window: int = 6

    # Prompt versioning (ADR-0009) — active prompt; rollback = set this back to a prior version
    prompt_version: str = "rag-v1"          # rag-v1 | rag-v2

    # Evaluation + MLOps (ADR-0008) — local file store, no server, $0
    mlflow_tracking_uri: str = "file:./mlruns"
    mlflow_experiment: str = "second-brain-rag"

    # API
    cors_origins: list[str] = ["http://localhost:3000"]

    # Daily briefing + scheduled pipelines (Phase 5, ADR-0013)
    briefing_lookback_hours: int = 24       # first-ever briefing window when no prior period_end
    job_max_attempts: int = 3               # worker retries a failing job up to this many times
    worker_poll_seconds: float = 5.0        # --loop poll interval (OS cron enqueues; D2)

    # Productionization + data governance (Phase 6, ADR-0012)
    admin_token: str | None = None          # bearer token guarding destructive/admin endpoints
    retention_raw_text_days: int = 180      # null documents.raw_text this long after embedding
    metrics_enabled: bool = True            # expose Prometheus /metrics + request middleware
    audit_enabled: bool = True              # write audit_log rows on governed data actions
    pgbouncer_url: str | None = None         # optional pooled DSN for the always-on service

    # Local-first Obsidian pivot (ADR-0015). The vault is the canonical private memory;
    # Postgres is a rebuildable derived index over these Markdown files.
    vault_path: str = str(Path.home() / "SecondBrainVault")
    vault_index_include_dirs: list[str] = []  # empty = all vault folders, after excludes
    vault_index_exclude_dirs: list[str] = [".obsidian", "Templates", "90 Archive"]
    mcp_approval_token: str | None = None  # optional local human token for approve_tool_call


settings = Settings()
