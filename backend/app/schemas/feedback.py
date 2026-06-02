"""Pydantic v2 schemas for POST /feedback."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    message_id: int
    rating: int = Field(..., description="1 = thumbs up, -1 = thumbs down")
    comment: str | None = None


class FeedbackResponse(BaseModel):
    id: int
    message_id: int
    rating: int
    comment: str | None
    created_at: datetime
