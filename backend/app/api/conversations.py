"""Conversation history plus feedback capture/review endpoints."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import deps
from app.chat.prompt import parse_citations
from app.db.models import Conversation, Feedback, Message
from app.retrieval.hybrid import load_display_chunks
from app.schemas.chat import CitationOut
from app.schemas.conversations import (
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationSummary,
    MessageOut,
    RetrievalOut,
)
from app.schemas.feedback import (
    EvalCandidate,
    EvalCandidateExportResponse,
    FeedbackAnalyticsResponse,
    FeedbackDocumentStats,
    FeedbackModelStats,
    FeedbackRequest,
    FeedbackResponse,
    FeedbackRetrievalContext,
    FeedbackTrendBucket,
    NegativeFeedbackItem,
    NegativeFeedbackListResponse,
)

router = APIRouter()


def _rate(negative: int, total: int) -> float:
    return negative / total if total else 0.0


def _retrievals_for_message(message: Message) -> list[FeedbackRetrievalContext]:
    return [
        FeedbackRetrievalContext(
            chunk_id=r.chunk_id,
            rank=r.rank,
            score=r.score,
            vector_score=r.vector_score,
            fulltext_score=r.fulltext_score,
            method=r.method,
        )
        for r in sorted(message.retrievals, key=lambda r: r.rank)
    ]


def _citations_for_message(
    db: Session, message: Message, display: dict[int, Any] | None = None
) -> list[CitationOut]:
    if message.role != "assistant" or not message.retrievals:
        return []

    retrievals = sorted(message.retrievals, key=lambda r: r.rank)
    used = parse_citations(message.content, len(retrievals))
    if not used:
        return []

    display_chunks = display if display is not None else load_display_chunks(
        db, [r.chunk_id for r in retrievals]
    )
    citations: list[CitationOut] = []
    for marker, retrieval in enumerate(retrievals, start=1):
        if marker not in used:
            continue
        display_chunk = display_chunks.get(retrieval.chunk_id)
        if display_chunk is None:
            continue
        citations.append(
            CitationOut(
                marker=marker,
                chunk_id=retrieval.chunk_id,
                document_id=display_chunk.document_id,
                document_title=display_chunk.document_title,
                source_id=display_chunk.source_id,
                source_name=display_chunk.source_name,
                snippet=display_chunk.content,
                score=retrieval.score,
                vector_score=retrieval.vector_score,
                fulltext_score=retrieval.fulltext_score,
                method=retrieval.method,
                char_start=display_chunk.char_start,
                char_end=display_chunk.char_end,
            )
        )
    return citations


def _previous_user_message(db: Session, message: Message) -> Message | None:
    return db.scalars(
        select(Message)
        .where(
            Message.conversation_id == message.conversation_id,
            Message.role == "user",
            Message.id < message.id,
        )
        .order_by(Message.id.desc())
        .limit(1)
    ).first()


def _feedback_cutoff(days: int) -> datetime:
    start_date = (datetime.now(timezone.utc) - timedelta(days=days - 1)).date()
    return datetime.combine(start_date, time.min, tzinfo=timezone.utc)


def _negative_feedback_items(
    db: Session, *, limit: int, offset: int, days: int | None = None
) -> tuple[list[NegativeFeedbackItem], int]:
    filters = [Feedback.rating == -1]
    if days is not None:
        filters.append(Feedback.created_at >= _feedback_cutoff(days))

    total = db.scalar(select(func.count(Feedback.id)).where(*filters)) or 0
    feedback_rows = db.scalars(
        select(Feedback)
        .where(*filters)
        .options(
            selectinload(Feedback.message).selectinload(Message.retrievals),
            selectinload(Feedback.message).selectinload(Message.conversation),
        )
        .order_by(Feedback.created_at.desc(), Feedback.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    items: list[NegativeFeedbackItem] = []
    for feedback in feedback_rows:
        message = feedback.message
        question = _previous_user_message(db, message)
        items.append(
            NegativeFeedbackItem(
                feedback_id=feedback.id,
                rating=feedback.rating,
                comment=feedback.comment,
                feedback_created_at=feedback.created_at,
                conversation_id=message.conversation_id,
                conversation_title=message.conversation.title if message.conversation else None,
                message_id=message.id,
                message_created_at=message.created_at,
                question_message_id=question.id if question else None,
                question=question.content if question else None,
                answer=message.content,
                model=message.model,
                latency_ms=message.latency_ms,
                retrievals=_retrievals_for_message(message),
                citations=_citations_for_message(db, message),
            )
        )
    return items, total


def _candidate_from_negative(item: NegativeFeedbackItem) -> EvalCandidate:
    expected_docs: list[str] = []
    for citation in item.citations:
        if citation.document_title not in expected_docs:
            expected_docs.append(citation.document_title)

    return EvalCandidate(
        id=f"feedback-{item.feedback_id}",
        question=item.question or "",
        expected_docs=expected_docs,
        expected_keywords=[],
        expect_refusal=False,
        metadata={
            "feedback_id": item.feedback_id,
            "conversation_id": item.conversation_id,
            "message_id": item.message_id,
            "comment": item.comment,
            "answer": item.answer,
            "model": item.model,
            "needs_review": True,
            "review_hint": (
                "expected_docs were inferred from cited documents; edit labels before "
                "adding to the fixed eval set"
            ),
            "citations": [citation.model_dump(mode="json") for citation in item.citations],
        },
    )


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    db: Session = Depends(deps.get_db),
):
    rows = db.execute(
        select(
            Conversation.id,
            Conversation.title,
            Conversation.created_at,
            Conversation.updated_at,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
    ).all()

    convs = [
        ConversationSummary(
            id=r.id,
            title=r.title,
            created_at=r.created_at,
            updated_at=r.updated_at,
            message_count=r.message_count,
        )
        for r in rows
    ]
    return ConversationListResponse(conversations=convs, total=len(convs))


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(deps.get_db),
):
    conv = db.get(
        Conversation,
        conversation_id,
        options=[
            selectinload(Conversation.messages).selectinload(Message.retrievals)
        ],
    )
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    ordered = sorted(conv.messages, key=lambda m: m.created_at)

    all_chunk_ids = [r.chunk_id for m in ordered for r in m.retrievals]
    display = load_display_chunks(db, all_chunk_ids) if all_chunk_ids else {}

    messages_out = [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            model=m.model,
            latency_ms=m.latency_ms,
            created_at=m.created_at,
            retrievals=[
                RetrievalOut(
                    chunk_id=r.chunk_id,
                    rank=r.rank,
                    score=r.score,
                    vector_score=r.vector_score,
                    fulltext_score=r.fulltext_score,
                    method=r.method,
                )
                for r in m.retrievals
            ],
            citations=_citations_for_message(db, m, display),
        )
        for m in ordered
    ]
    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=messages_out,
    )


@router.get("/feedback/analytics", response_model=FeedbackAnalyticsResponse)
def feedback_analytics(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(deps.get_db),
):
    cutoff = _feedback_cutoff(days)
    feedback_rows = db.scalars(
        select(Feedback)
        .where(Feedback.created_at >= cutoff)
        .options(selectinload(Feedback.message).selectinload(Message.retrievals))
        .order_by(Feedback.created_at.asc(), Feedback.id.asc())
    ).all()

    total = len(feedback_rows)
    positive = sum(1 for feedback in feedback_rows if feedback.rating == 1)
    negative = sum(1 for feedback in feedback_rows if feedback.rating == -1)
    latest = max((feedback.created_at for feedback in feedback_rows), default=None)

    by_date: dict[date, dict[str, int]] = {
        (cutoff.date() + timedelta(days=i)): {"positive": 0, "negative": 0}
        for i in range(days)
    }
    by_model: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"positive": 0, "negative": 0, "latency_total": 0.0, "latency_count": 0}
    )
    negative_documents: Counter[tuple[int, str, int, str]] = Counter()

    for feedback in feedback_rows:
        bucket = by_date.setdefault(feedback.created_at.date(), {"positive": 0, "negative": 0})
        key = "positive" if feedback.rating == 1 else "negative"
        bucket[key] += 1

        message = feedback.message
        model_key = message.model or "unknown"
        by_model[model_key][key] += 1
        if message.latency_ms is not None:
            by_model[model_key]["latency_total"] += float(message.latency_ms)
            by_model[model_key]["latency_count"] += 1

        if feedback.rating == -1:
            seen_docs: set[tuple[int, str, int, str]] = set()
            for citation in _citations_for_message(db, message):
                seen_docs.add(
                    (
                        citation.document_id,
                        citation.document_title,
                        citation.source_id,
                        citation.source_name,
                    )
                )
            negative_documents.update(seen_docs)

    trend = []
    for bucket_date in sorted(by_date):
        counts = by_date[bucket_date]
        bucket_total = counts["positive"] + counts["negative"]
        trend.append(
            FeedbackTrendBucket(
                date=bucket_date,
                total=bucket_total,
                positive=counts["positive"],
                negative=counts["negative"],
                negative_rate=_rate(counts["negative"], bucket_total),
            )
        )

    model_stats: list[FeedbackModelStats] = []
    for model, counts in by_model.items():
        model_total = int(counts["positive"] + counts["negative"])
        latency_count = int(counts["latency_count"])
        model_stats.append(
            FeedbackModelStats(
                model=model,
                total=model_total,
                positive=int(counts["positive"]),
                negative=int(counts["negative"]),
                negative_rate=_rate(int(counts["negative"]), model_total),
                avg_latency_ms=(
                    float(counts["latency_total"]) / latency_count if latency_count else None
                ),
            )
        )
    model_stats.sort(key=lambda item: (-item.negative, -item.total, item.model))

    top_documents = [
        FeedbackDocumentStats(
            document_id=document_id,
            document_title=document_title,
            source_id=source_id,
            source_name=source_name,
            negative=count,
        )
        for (document_id, document_title, source_id, source_name), count
        in negative_documents.most_common(10)
    ]

    return FeedbackAnalyticsResponse(
        window_days=days,
        total=total,
        positive=positive,
        negative=negative,
        negative_rate=_rate(negative, total),
        latest_feedback_at=latest,
        trend=trend,
        by_model=model_stats,
        top_negative_documents=top_documents,
    )


@router.get("/feedback/negative", response_model=NegativeFeedbackListResponse)
def list_negative_feedback(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    days: int | None = Query(default=None, ge=1, le=365),
    db: Session = Depends(deps.get_db),
):
    items, total = _negative_feedback_items(db, limit=limit, offset=offset, days=days)
    return NegativeFeedbackListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/feedback/eval-candidates", response_model=EvalCandidateExportResponse)
def feedback_eval_candidates(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    days: int | None = Query(default=None, ge=1, le=365),
    db: Session = Depends(deps.get_db),
):
    items, total = _negative_feedback_items(db, limit=limit, offset=offset, days=days)
    return EvalCandidateExportResponse(
        generated_at=datetime.now(timezone.utc),
        source="feedback",
        total=total,
        cases=[_candidate_from_negative(item) for item in items],
    )


@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def create_feedback(
    req: FeedbackRequest,
    db: Session = Depends(deps.get_db),
):
    if req.rating not in (1, -1):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="rating must be 1 or -1",
        )
    msg = db.get(Message, req.message_id)
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    fb = Feedback(message_id=req.message_id, rating=req.rating, comment=req.comment)
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return FeedbackResponse(
        id=fb.id,
        message_id=fb.message_id,
        rating=fb.rating,
        comment=fb.comment,
        created_at=fb.created_at,
    )
