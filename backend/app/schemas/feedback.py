"""Pydantic v2 schemas for feedback capture and review."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.chat import CitationOut


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


class FeedbackTrendBucket(BaseModel):
    date: date
    total: int
    positive: int
    negative: int
    negative_rate: float


class FeedbackModelStats(BaseModel):
    model: str
    total: int
    positive: int
    negative: int
    negative_rate: float
    avg_latency_ms: float | None


class FeedbackDocumentStats(BaseModel):
    document_id: int
    document_title: str
    source_id: int
    source_name: str
    negative: int


class FeedbackAnalyticsResponse(BaseModel):
    window_days: int
    total: int
    positive: int
    negative: int
    negative_rate: float
    latest_feedback_at: datetime | None
    trend: list[FeedbackTrendBucket]
    by_model: list[FeedbackModelStats]
    top_negative_documents: list[FeedbackDocumentStats]


class FeedbackRetrievalContext(BaseModel):
    chunk_id: int
    rank: int
    score: float | None
    vector_score: float | None
    fulltext_score: float | None
    method: str


class NegativeFeedbackItem(BaseModel):
    feedback_id: int
    rating: int
    comment: str | None
    feedback_created_at: datetime
    conversation_id: int
    conversation_title: str | None
    message_id: int
    message_created_at: datetime
    question_message_id: int | None
    question: str | None
    answer: str
    model: str | None
    latency_ms: int | None
    retrievals: list[FeedbackRetrievalContext]
    citations: list[CitationOut]


class NegativeFeedbackListResponse(BaseModel):
    items: list[NegativeFeedbackItem]
    total: int
    limit: int
    offset: int


class EvalCandidate(BaseModel):
    id: str
    question: str
    expected_docs: list[str] = Field(default_factory=list)
    expected_keywords: list[str] = Field(default_factory=list)
    expect_refusal: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalCandidateExportResponse(BaseModel):
    generated_at: datetime
    source: str
    total: int
    cases: list[EvalCandidate]


class EvalCaseReviewConfirmations(BaseModel):
    expected_docs: bool
    expected_keywords: bool
    expect_refusal: bool


class PromoteEvalCandidateRequest(BaseModel):
    id: str
    question: str
    expected_docs: list[str] = Field(default_factory=list)
    expected_keywords: list[str] = Field(default_factory=list)
    expect_refusal: bool
    confirmations: EvalCaseReviewConfirmations


class PromoteEvalCandidateResponse(BaseModel):
    promoted_at: datetime
    dataset_path: str
    case: EvalCandidate
