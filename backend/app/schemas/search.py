"""Pydantic v2 schemas for GET /search."""
from __future__ import annotations

from pydantic import BaseModel


class SearchHit(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    source_id: int
    source_name: str
    snippet: str
    score: float
    vector_score: float | None
    fulltext_score: float | None
    method: str
    char_start: int | None
    char_end: int | None


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]
    retrieval: dict
