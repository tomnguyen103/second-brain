"""Pydantic v2 schemas for GET /conversations endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.chat import CitationOut


class ConversationSummary(BaseModel):
    id: int
    title: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]
    total: int
    limit: int
    offset: int


class RetrievalOut(BaseModel):
    chunk_id: int
    rank: int
    score: float | None
    vector_score: float | None
    fulltext_score: float | None
    method: str


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    model: str | None
    latency_ms: int | None
    created_at: datetime
    retrievals: list[RetrievalOut]
    citations: list[CitationOut] = []


class ConversationDetailResponse(BaseModel):
    id: int
    title: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut]
