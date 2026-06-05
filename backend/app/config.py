"""Application settings."""
from __future__ import annotations

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
    # Filter weak vector-only context before fusion. Full-text candidates still pass through
    # because `tsv @@ query` is already a lexical relevance gate on exact terms.
    retrieval_min_vector_score: float = 0.08
    retrieval_query_rewrite_enabled: bool = False
    retrieval_query_rewrite_max_chars: int = 240

    # Chat (ADR-0006)
    history_window: int = 6

    # Prompt versioning (ADR-0009) — active prompt; rollback = set this back to a prior version
    prompt_version: str = "rag-v1"          # rag-v1 | rag-v2

    # Evaluation + MLOps (ADR-0008) — local file store, no server, $0
    mlflow_tracking_uri: str = "file:./mlruns"
    mlflow_experiment: str = "second-brain-rag"

    # API
    cors_origins: list[str] = ["http://localhost:3000"]
    # Single-user API bearer token for notes, conversations, sources, tasks, feedback, and
    # research endpoints. None keeps local/dev tests keyless; prod compose requires it.
    api_token: str | None = None

    # Redis-backed optional paths. Local development defaults Redis off; prod compose enables it.
    redis_enabled: bool = False
    redis_url: str = "redis://localhost:6379/0"
    redis_socket_timeout_seconds: float = 0.25
    rate_limit_enabled: bool = True
    # When Redis is enabled but unavailable, deny rate-limited mutation/chat traffic by default
    # instead of silently removing protection. Can be relaxed only as an explicit ops decision.
    rate_limit_fail_closed: bool = True
    # X-Forwarded-For is spoofable unless every caller reaches the app through a trusted proxy.
    trust_forwarded_for: bool = False
    chat_rate_limit_requests: int = 30
    chat_rate_limit_window_seconds: int = 60
    ingest_rate_limit_requests: int = 10
    ingest_rate_limit_window_seconds: int = 60
    search_cache_enabled: bool = True
    search_cache_ttl_seconds: int = 120
    embedding_cache_enabled: bool = True
    embedding_cache_ttl_seconds: int = 604800

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
    # MCP clients are trusted local processes. Keep durable mutations off unless explicitly enabled.
    mcp_enable_mutations: bool = False


settings = Settings()
