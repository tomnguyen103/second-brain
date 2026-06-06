"""Pydantic schemas for source/document overview endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class SourceUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=240)


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


class DocumentUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=400)


class DocumentContentUpdateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2_000_000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value


class DocumentContentResponse(BaseModel):
    source: SourceOut
    document: DocumentSummary
    content: str | None
    content_source: str
    truncated: bool


class DeleteDocumentResponse(BaseModel):
    document_id: int
    source_id: int
    chunks_deleted: int
