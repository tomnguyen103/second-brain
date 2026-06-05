import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import deps
from app.cache.rate_limit import check_rate_limit, client_identity
from app.chat.service import ChatResult, chat, stream_chat
from app.config import Settings
from app.llm.base import supports_streaming
from app.schemas.chat import ChatRequest, ChatResponse, CitationOut, UsageOut

router = APIRouter(dependencies=[Depends(deps.require_api_access)])


def _check_chat_rate_limit(request: Request, redis_client, settings: Settings) -> None:
    """Apply the shared chat bucket to JSON and SSE chat endpoints."""
    decision = check_rate_limit(
        redis_client,
        settings,
        bucket="chat",
        identity=client_identity(request, settings),
        limit=settings.chat_rate_limit_requests,
        window_seconds=settings.chat_rate_limit_window_seconds,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="chat rate limit exceeded",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )


def _filters_from_request(req: ChatRequest) -> dict:
    filters = {}
    if req.filters.source_ids:
        filters["source_ids"] = req.filters.source_ids
    if req.filters.tags:
        filters["tags"] = req.filters.tags
    return filters


def _chat_response(result: ChatResult) -> ChatResponse:
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


def _format_sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def _stream_events(db: Session, embedder, llm, settings: Settings, req: ChatRequest,
                   filters: dict, redis_client) -> Iterator[str]:
    try:
        for event in stream_chat(
            db, embedder, llm, settings,
            message=req.message,
            conversation_id=req.conversation_id,
            top_k=req.top_k,
            filters=filters,
            include_chunks=req.options.include_chunks,
            redis_client=redis_client,
        ):
            if event.type == "delta":
                yield _format_sse("delta", {"text": event.text or ""})
            elif event.result is not None:
                yield _format_sse(
                    "complete",
                    _chat_response(event.result).model_dump(mode="json"),
                )
    except Exception:
        yield _format_sse("error", {"message": "streaming chat failed"})


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(
    request: Request,
    req: ChatRequest,
    db: Session = Depends(deps.get_db),
    embedder=Depends(deps.get_embedder),
    settings: Settings = Depends(deps.get_settings),
    redis_client=Depends(deps.get_redis),
):
    _check_chat_rate_limit(request, redis_client, settings)

    llm = deps.get_llm_client(settings, private_mode=req.options.private_mode)
    filters = _filters_from_request(req)

    result = chat(
        db, embedder, llm, settings,
        message=req.message,
        conversation_id=req.conversation_id,
        top_k=req.top_k,
        filters=filters,
        include_chunks=req.options.include_chunks,
        redis_client=redis_client,
    )

    return _chat_response(result)


@router.post("/chat/stream")
def chat_stream_endpoint(
    request: Request,
    req: ChatRequest,
    db: Session = Depends(deps.get_db),
    embedder=Depends(deps.get_embedder),
    settings: Settings = Depends(deps.get_settings),
    redis_client=Depends(deps.get_redis),
):
    _check_chat_rate_limit(request, redis_client, settings)

    llm = deps.get_llm_client(settings, private_mode=req.options.private_mode)
    if not supports_streaming(llm):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="streaming is unavailable for the selected LLM provider",
        )

    filters = _filters_from_request(req)
    return StreamingResponse(
        _stream_events(db, embedder, llm, settings, req, filters, redis_client),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
