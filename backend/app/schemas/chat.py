"""Pydantic v2 schemas for POST /chat (ADR-0007)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatFilters(BaseModel):
    source_ids: list[int] | None = None
    tags: list[str] | None = None


class ChatOptions(BaseModel):
    private_mode: bool = False
    include_chunks: bool = True
    agentic: bool = False


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None
    top_k: int | None = None
    filters: ChatFilters = Field(default_factory=ChatFilters)
    options: ChatOptions = Field(default_factory=ChatOptions)


class CitationOut(BaseModel):
    marker: int
    chunk_id: int
    document_id: int
    document_title: str
    source_id: int
    source_name: str
    snippet: str | None
    score: float | None
    vector_score: float | None
    fulltext_score: float | None
    method: str
    char_start: int | None
    char_end: int | None


class UsageOut(BaseModel):
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


class ChatResponse(BaseModel):
    conversation_id: int
    message_id: int
    answer: str
    citations: list[CitationOut]
    usage: UsageOut
    model: str | None
    latency_ms: int
    retrieval: dict
