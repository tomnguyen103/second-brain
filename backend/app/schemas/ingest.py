"""Pydantic v2 schemas for POST /ingest (ADR-0007)."""
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

TagName = Annotated[str, Field(min_length=1, max_length=80)]
MAX_DOCUMENT_CONTENT_CHARS = 2_000_000
MAX_INGEST_DOCUMENTS = 25
MAX_TAGS_PER_DOCUMENT = 50


class SourceIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    type: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=240)
    uri: str | None = Field(default=None, max_length=2_000)
    config: dict = Field(default_factory=dict)


class DocumentIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=400)
    content: str = Field(min_length=1, max_length=MAX_DOCUMENT_CONTENT_CHARS)
    external_id: str | None = Field(default=None, max_length=512)
    content_type: str | None = Field(default="text/plain", max_length=120)
    metadata: dict = Field(default_factory=dict)
    tags: list[TagName] = Field(default_factory=list, max_length=MAX_TAGS_PER_DOCUMENT)


class IngestRequest(BaseModel):
    source: SourceIn
    documents: list[DocumentIn] = Field(min_length=1, max_length=MAX_INGEST_DOCUMENTS)


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
