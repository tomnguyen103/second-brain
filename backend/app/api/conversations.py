"""GET /conversations, GET /conversations/{id}, POST /feedback."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import deps
from app.db.models import Conversation, Feedback, Message
from app.schemas.conversations import (
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationSummary,
    MessageOut,
    RetrievalOut,
)
from app.schemas.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter()


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
        )
        for m in sorted(conv.messages, key=lambda m: m.created_at)
    ]
    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=messages_out,
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
