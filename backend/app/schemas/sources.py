"""Pydantic schemas for source/document overview endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    name: str
    uri: str | None
    created_at: datetime
    updated_at: datetime


class SourceSummary(SourceOut):
    document_count: int
    chunk_count: int
    latest_document_at: datetime | None


class SourceListResponse(BaseModel):
    sources: list[SourceSummary]
    total: int


class DocumentSummary(BaseModel):
    id: int
    source_id: int
    title: str
    external_id: str | None
    content_type: str | None
    content_hash: str
    status: str
    tags: list[str]
    chunk_count: int
    raw_text_available: bool
    ingested_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    source: SourceOut
    documents: list[DocumentSummary]
    total: int
