from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import deps
from app.cache.rate_limit import check_rate_limit, client_identity
from app.chat.service import chat
from app.config import Settings
from app.schemas.chat import ChatRequest, ChatResponse, CitationOut, UsageOut

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(
    request: Request,
    req: ChatRequest,
    db: Session = Depends(deps.get_db),
    embedder=Depends(deps.get_embedder),
    settings: Settings = Depends(deps.get_settings),
    redis_client=Depends(deps.get_redis),
):
    decision = check_rate_limit(
        redis_client,
        settings,
        bucket="chat",
        identity=client_identity(request),
        limit=settings.chat_rate_limit_requests,
        window_seconds=settings.chat_rate_limit_window_seconds,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="chat rate limit exceeded",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )

    llm = deps.get_llm_client(settings, private_mode=req.options.private_mode)
    filters = {}
    if req.filters.source_ids:
        filters["source_ids"] = req.filters.source_ids
    if req.filters.tags:
        filters["tags"] = req.filters.tags

    result = chat(
        db, embedder, llm, settings,
        message=req.message,
        conversation_id=req.conversation_id,
        top_k=req.top_k,
        filters=filters,
        include_chunks=req.options.include_chunks,
        redis_client=redis_client,
    )

    citations_out = [
        CitationOut(
            marker=c.marker,
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            document_title=c.document_title,
            source_id=c.source_id,
            source_name=c.source_name,
            snippet=c.snippet,
            score=c.score,
            vector_score=c.vector_score,
            fulltext_score=c.fulltext_score,
            method=c.method,
            char_start=c.char_start,
            char_end=c.char_end,
        )
        for c in result.citations
    ]
    return ChatResponse(
        conversation_id=result.conversation_id,
        message_id=result.message_id,
        answer=result.answer,
        citations=citations_out,
        usage=UsageOut(
            prompt_tokens=result.usage.get("prompt_tokens"),
            completion_tokens=result.usage.get("completion_tokens"),
            total_tokens=result.usage.get("total_tokens"),
        ),
        model=result.model,
        latency_ms=result.latency_ms,
        retrieval=result.retrieval,
    )
