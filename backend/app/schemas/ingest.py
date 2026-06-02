"""Pydantic v2 schemas for POST /ingest (ADR-0007)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SourceIn(BaseModel):
    type: str
    name: str
    uri: str | None = None
    config: dict = Field(default_factory=dict)


class DocumentIn(BaseModel):
    title: str
    content: str
    external_id: str | None = None
    content_type: str | None = "text/plain"
    metadata: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class IngestRequest(BaseModel):
    source: SourceIn
    documents: list[DocumentIn]


class DocumentOut(BaseModel):
    document_id: int | None
    title: str
    status: str
    content_hash: str
    chunk_count: int = 0
    embedded_count: int = 0
    duplicate_of: int | None = None
    error: str | None = None


class IngestSummary(BaseModel):
    received: int
    embedded: int
    duplicates: int
    failed: int
    chunks_created: int


class IngestResponse(BaseModel):
    source_id: int
    documents: list[DocumentOut]
    summary: IngestSummary
