"""Pydantic schemas for queued research job endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

JobStatus = Literal["queued", "running", "done", "failed"]


class ResearchSourceText(BaseModel):
    title: str | None = None
    text: str
    uri: str | None = None


class ResearchJobCreateRequest(BaseModel):
    topic: str
    source_urls: list[str] = Field(default_factory=list)
    source_texts: list[ResearchSourceText] = Field(default_factory=list)


class ResearchJobOut(BaseModel):
    id: int
    type: Literal["research"]
    topic: str | None
    status: JobStatus
    attempts: int
    last_error: str | None
    scheduled_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    result: dict | None


class ResearchJobListResponse(BaseModel):
    jobs: list[ResearchJobOut]
    total: int
