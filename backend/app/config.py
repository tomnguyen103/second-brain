"""Application settings."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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
    gemini_model: str = "gemini-1.5-flash"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # Embeddings (ADR-0002)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

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


settings = Settings()
