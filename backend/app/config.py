"""Application settings. Phase 0 needs only the database URL."""
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
    # Host port 5433 (not 5432): the Docker DB is published on 5433 to avoid a clash with a
    # native PostgreSQL on this machine. See docker-compose.yml and docs/implementation-notes.md.
    database_url: str = "postgresql+psycopg://second_brain:second_brain@localhost:5433/second_brain"


settings = Settings()
