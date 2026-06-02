"""Pydantic schemas for the briefing API (Phase 5)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BriefingOut(BaseModel):
    # protected_namespaces=() allows the `model` field name (pydantic reserves `model_*`).
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    summary: str
    body_markdown: str
    document_count: int
    model: str | None


class BriefingListResponse(BaseModel):
    briefings: list[BriefingOut]
    total: int
