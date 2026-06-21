"""Pydantic schemas for queued research job endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_RESEARCH_SOURCES = 8
MAX_RESEARCH_SOURCE_TEXT_CHARS = 12_000
MAX_RESEARCH_TOPIC_CHARS = 400
ResearchUrl = Annotated[str, Field(min_length=1, max_length=2_000)]

JobStatus = Literal["queued", "running", "done", "failed"]


class ResearchSourceText(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, max_length=400)
    text: str = Field(min_length=1, max_length=MAX_RESEARCH_SOURCE_TEXT_CHARS)
    uri: str | None = Field(default=None, max_length=2_000)


class ResearchJobCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    topic: str = Field(min_length=1, max_length=MAX_RESEARCH_TOPIC_CHARS)
    source_urls: list[ResearchUrl] = Field(default_factory=list, max_length=MAX_RESEARCH_SOURCES)
    source_texts: list[ResearchSourceText] = Field(default_factory=list, max_length=MAX_RESEARCH_SOURCES)

    @model_validator(mode="after")
    def limit_combined_sources(self) -> "ResearchJobCreateRequest":
        if len(self.source_urls) + len(self.source_texts) > MAX_RESEARCH_SOURCES:
            raise ValueError(f"at most {MAX_RESEARCH_SOURCES} research sources are supported")
        return self


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
