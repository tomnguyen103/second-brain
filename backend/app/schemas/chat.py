"""Pydantic v2 schemas for POST /chat (ADR-0007)."""
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

FilterTag = Annotated[str, Field(min_length=1, max_length=80)]
MAX_CHAT_MESSAGE_CHARS = 20_000
MAX_CHAT_FILTER_VALUES = 50
MAX_CHAT_TOP_K = 20


class ChatFilters(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source_ids: list[int] | None = Field(default=None, max_length=MAX_CHAT_FILTER_VALUES)
    tags: list[FilterTag] | None = Field(default=None, max_length=MAX_CHAT_FILTER_VALUES)


class ChatOptions(BaseModel):
    private_mode: bool = False
    include_chunks: bool = True
    agentic: bool = False


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=MAX_CHAT_MESSAGE_CHARS)
    conversation_id: int | None = None
    top_k: int | None = Field(default=None, ge=1, le=MAX_CHAT_TOP_K)
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
