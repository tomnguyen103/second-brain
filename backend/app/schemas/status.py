"""Schemas for the local operator status endpoint."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DatabaseStatus(BaseModel):
    reachable: bool
    migration_current: str | None
    migration_head: str | None
    migrated: bool
    error: str | None = None


class WorkerStatus(BaseModel):
    status: str
    queued: int
    running: int
    done: int
    failed: int
    latest_finished_at: datetime | None
    latest_error: str | None


class KnowledgeStatus(BaseModel):
    source_count: int
    document_count: int
    embedded_document_count: int
    chunk_count: int
    embedding_count: int
    latest_document_at: datetime | None


class RuntimeStatus(BaseModel):
    llm_provider: str
    llm_model: str
    embedding_provider: str
    embedding_model: str
    agentic_rag_enabled: bool
    mcp_mutations_enabled: bool


class AppStatusResponse(BaseModel):
    status: str
    database: DatabaseStatus
    worker: WorkerStatus
    knowledge: KnowledgeStatus
    runtime: RuntimeStatus
