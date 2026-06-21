from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.ingest import DocumentOut, IngestSummary

CaptureTag = Annotated[str, Field(min_length=1, max_length=80)]
MAX_CAPTURE_TEXT_CHARS = 200_000
MAX_CAPTURE_TAGS = 50


class CaptureRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    url: str = Field(min_length=1, max_length=2_000)
    title: str | None = Field(default=None, max_length=400)
    notes: str | None = Field(default=None, max_length=MAX_CAPTURE_TEXT_CHARS)
    selected_text: str | None = Field(default=None, max_length=MAX_CAPTURE_TEXT_CHARS)
    tags: list[CaptureTag] = Field(default_factory=list, max_length=MAX_CAPTURE_TAGS)

    @model_validator(mode="after")
    def require_captured_text(self) -> "CaptureRequest":
        if not (self.notes or "").strip() and not (self.selected_text or "").strip():
            raise ValueError("capture requires notes or selected_text")
        return self


class CaptureResponse(BaseModel):
    source_id: int
    capture_url: str
    document: DocumentOut
    summary: IngestSummary
