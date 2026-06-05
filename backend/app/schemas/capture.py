from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.schemas.ingest import DocumentOut, IngestSummary


class CaptureRequest(BaseModel):
    url: str
    title: str | None = None
    notes: str | None = None
    selected_text: str | None = None
    tags: list[str] = Field(default_factory=list)

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
