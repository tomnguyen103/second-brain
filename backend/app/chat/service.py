"""Chat orchestration — retrieve → prompt → generate → persist (ADR-0006/0007)."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chat.prompt import ContextItem, all_citation_markers, build_messages, get_prompt
from app.config import Settings
from app.db.models import Conversation, Message, Retrieval
from app.llm.base import LLMMessage, supports_streaming
from app.retrieval.hybrid import hybrid_search, load_display_chunks
from app.retrieval.query import maybe_rewrite_query


@dataclass
class Citation:
    marker: int
    chunk_id: int
    document_id: int
    document_title: str
    source_id: int
    source_name: str
    score: float | None
    vector_score: float | None
    fulltext_score: float | None
    method: str
    snippet: str | None = None
    char_start: int | None = None
    char_end: int | None = None


@dataclass
class ChatResult:
    conversation_id: int
    message_id: int
    answer: str
    citations: list[Citation]
    usage: dict
    model: str | None
    latency_ms: int
    retrieval: dict = field(default_factory=dict)


@dataclass
class ChatStreamEvent:
    type: Literal["delta", "complete"]
    text: str | None = None
    result: ChatResult | None = None


class StreamingUnavailable(RuntimeError):
    """Raised when a selected LLM provider cannot stream tokens."""


CITATION_FAILURE_TEXT = (
    "I found related notes, but could not produce a properly cited answer from them. "
    "Please try again."
)

_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")
_SEGMENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_SUPPORT_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_'-]{1,}")
_SUPPORT_STOPWORDS = {
    "about", "above", "after", "again", "also", "because", "been", "before", "being",
    "below", "between", "could", "does", "doing", "from", "have", "into", "just",
    "like", "more", "most", "need", "needs", "only", "over", "same", "should",
    "that", "their", "them", "then", "there", "these", "they", "this", "those",
    "through", "using", "very", "what", "when", "where", "which", "while", "with",
    "would", "your",
}


@dataclass
class _PreparedChat:
    conversation_id: int
    messages: list[LLMMessage]
    hits: list
    display: dict
    meta: dict
    item_count: int
    include_chunks: bool


def _support_tokens(text: str) -> set[str]:
    return {
        token.strip("'")
        for token in _SUPPORT_TOKEN_RE.findall((text or "").lower())
        if token.strip("'") and token not in _SUPPORT_STOPWORDS and not token.isdigit()
    }


def _claim_segments(answer: str) -> list[str]:
    segments = []
    for raw in _SEGMENT_SPLIT_RE.split(answer or ""):
        segment = raw.strip(" \t-*•")
        if segment:
            segments.append(segment)
    return segments


def _context_tokens(prepared: _PreparedChat, marker: int) -> set[str]:
    hit = prepared.hits[marker - 1]
    dc = prepared.display[hit.chunk_id]
    return _support_tokens(f"{dc.source_name} {dc.document_title} {dc.content}")


def _citation_support_failures(answer: str, prepared: _PreparedChat) -> list[dict]:
    """Return answer segments whose cited marker does not plausibly support the claim.

    This is a conservative lexical guard, not a semantic verifier. It blocks obvious prompt
    injection/hallucination where a valid marker is pasted onto unrelated text.
    """
    failures: list[dict] = []
    for segment in _claim_segments(answer):
        markers = [
            int(match.group(1))
            for match in _CITATION_MARKER_RE.finditer(segment)
            if 1 <= int(match.group(1)) <= prepared.item_count
        ]
        claim_text = _CITATION_MARKER_RE.sub("", segment)
        claim_tokens = _support_tokens(claim_text)
        if not claim_tokens:
            continue
        if not markers:
            failures.append({"reason": "missing_segment_citation", "segment": segment[:160]})
            continue

        cited_tokens: set[str] = set()
        for marker in markers:
            cited_tokens.update(_context_tokens(prepared, marker))
        overlap = claim_tokens & cited_tokens
        min_overlap = 1 if len(claim_tokens) <= 4 else 2
        if len(overlap) < min_overlap:
            failures.append({
                "reason": "unsupported_segment",
                "segment": segment[:160],
                "markers": markers,
                "overlap": sorted(overlap)[:10],
            })
    return failures


def _history(db: Session, conversation_id: int, window: int) -> list[LLMMessage]:
    rows = db.scalars(
        select(Message).where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc()).limit(window)).all()
    return [LLMMessage(m.role, m.content) for m in reversed(rows)]


def _prepare_chat(db: Session, embedder, llm, settings: Settings, *, message: str,
                  conversation_id: int | None = None, top_k: int | None = None,
                  filters: dict | None = None, include_chunks: bool = True,
                  redis_client=None) -> _PreparedChat | ChatResult:
    filters = filters or {}
    if conversation_id is None:
        conv = Conversation(title=message[:80])
        db.add(conv)
        db.flush()
        conversation_id = conv.id

    history = _history(db, conversation_id, settings.history_window)
    db.add(Message(conversation_id=conversation_id, role="user", content=message))
    db.flush()

    retrieval_query, rewrite_meta = maybe_rewrite_query(llm, settings, message)
    hits, meta = hybrid_search(db, embedder, settings, retrieval_query,
                               top_k=top_k, source_ids=filters.get("source_ids"),
                               tags=filters.get("tags"), redis_client=redis_client)
    meta = {**meta, **rewrite_meta}

    # No usable context: either no candidates exist, or vector-only candidates were too weak.
    if not hits:
        refusal = get_prompt(settings.prompt_version).refusal_text
        assistant = Message(conversation_id=conversation_id, role="assistant",
                            content=refusal, model=None)
        db.add(assistant)
        db.commit()
        reason = "weak_context" if meta.get("weak_context") else "empty_context"
        return ChatResult(conversation_id, assistant.id, refusal, [],
                          {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                          None, 0, {**meta, "fused_returned": 0,
                                    "refusal_reason": reason})

    display = load_display_chunks(db, [h.chunk_id for h in hits])
    items = [ContextItem(i + 1, display[h.chunk_id].source_name,
                         display[h.chunk_id].document_title, display[h.chunk_id].content)
             for i, h in enumerate(hits)]
    messages = build_messages(message, items, history, prompt_version=settings.prompt_version)
    return _PreparedChat(conversation_id, messages, hits, display, meta, len(items), include_chunks)


def _finalize_chat(db: Session, prepared: _PreparedChat, *, answer: str, model: str | None,
                   usage: dict, latency_ms: int) -> ChatResult:
    emitted_markers = all_citation_markers(answer)
    invalid_markers = [i for i in emitted_markers if i < 1 or i > prepared.item_count]
    cited = [i for i in emitted_markers if 1 <= i <= prepared.item_count]
    support_failures = (
        [] if invalid_markers or not cited else _citation_support_failures(answer, prepared)
    )
    if invalid_markers or not cited or support_failures:
        answer = CITATION_FAILURE_TEXT
        prepared.meta = {
            **prepared.meta,
            "citation_validation_failed": True,
            "citation_failure_reason": (
                "invalid_citations"
                if invalid_markers
                else "missing_citations"
                if not cited
                else "unsupported_claims"
            ),
            "invalid_citation_markers": invalid_markers,
            "unsupported_citation_segments": support_failures,
        }
        cited = []
    assistant = Message(conversation_id=prepared.conversation_id, role="assistant",
                        content=answer, model=model, token_usage=usage,
                        latency_ms=latency_ms)
    db.add(assistant)
    db.flush()

    citations: list[Citation] = []
    for i, h in enumerate(prepared.hits):
        marker = i + 1
        db.add(Retrieval(message_id=assistant.id, chunk_id=h.chunk_id, rank=h.rank,
                         score=h.score, vector_score=h.vector_score,
                         fulltext_score=h.fulltext_score, method=h.method))
        if marker in cited:
            dc = prepared.display[h.chunk_id]
            citations.append(Citation(
                marker=marker, chunk_id=h.chunk_id, document_id=dc.document_id,
                document_title=dc.document_title, source_id=dc.source_id,
                source_name=dc.source_name, score=h.score, vector_score=h.vector_score,
                fulltext_score=h.fulltext_score, method=h.method,
                snippet=dc.content if prepared.include_chunks else None,
                char_start=dc.char_start if prepared.include_chunks else None,
                char_end=dc.char_end if prepared.include_chunks else None))

    db.commit()
    return ChatResult(prepared.conversation_id, assistant.id, answer, citations, usage,
                      model, latency_ms, prepared.meta)


def chat(db: Session, embedder, llm, settings: Settings, *, message: str,
         conversation_id: int | None = None, top_k: int | None = None,
         filters: dict | None = None, include_chunks: bool = True,
         redis_client=None) -> ChatResult:
    prepared = _prepare_chat(
        db, embedder, llm, settings,
        message=message,
        conversation_id=conversation_id,
        top_k=top_k,
        filters=filters,
        include_chunks=include_chunks,
        redis_client=redis_client,
    )
    if isinstance(prepared, ChatResult):
        return prepared

    started = time.perf_counter()
    resp = llm.generate(prepared.messages)
    latency_ms = int((time.perf_counter() - started) * 1000)

    usage = {"prompt_tokens": resp.prompt_tokens, "completion_tokens": resp.completion_tokens,
             "total_tokens": resp.total_tokens}
    return _finalize_chat(db, prepared, answer=resp.text, model=resp.model,
                          usage=usage, latency_ms=latency_ms)


def stream_chat(db: Session, embedder, llm, settings: Settings, *, message: str,
                conversation_id: int | None = None, top_k: int | None = None,
                filters: dict | None = None, include_chunks: bool = True,
                redis_client=None):
    if not supports_streaming(llm):
        raise StreamingUnavailable(f"{getattr(llm, 'model', 'selected model')} cannot stream")

    prepared = _prepare_chat(
        db, embedder, llm, settings,
        message=message,
        conversation_id=conversation_id,
        top_k=top_k,
        filters=filters,
        include_chunks=include_chunks,
        redis_client=redis_client,
    )
    if isinstance(prepared, ChatResult):
        yield ChatStreamEvent(type="complete", result=prepared)
        return

    started = time.perf_counter()
    parts: list[str] = []
    delta_parts: list[str] = []
    usage = {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    model = getattr(llm, "model", None)
    try:
        for chunk in llm.generate_stream(prepared.messages):
            if chunk.model:
                model = chunk.model
            if chunk.prompt_tokens is not None:
                usage["prompt_tokens"] = chunk.prompt_tokens
            if chunk.completion_tokens is not None:
                usage["completion_tokens"] = chunk.completion_tokens
            if chunk.total_tokens is not None:
                usage["total_tokens"] = chunk.total_tokens
            if chunk.text:
                parts.append(chunk.text)
                delta_parts.append(chunk.text)

        latency_ms = int((time.perf_counter() - started) * 1000)
        raw_answer = "".join(parts)
        result = _finalize_chat(db, prepared, answer=raw_answer, model=model,
                                usage=usage, latency_ms=latency_ms)
        # Retrieved notes are untrusted input. Do not send provider chunks until the
        # assembled answer passes citation validation, otherwise prompt-injected text
        # could leak over SSE before the final response is replaced.
        if not result.retrieval.get("citation_validation_failed") and result.answer == raw_answer:
            for text in delta_parts:
                yield ChatStreamEvent(type="delta", text=text)
        yield ChatStreamEvent(type="complete", result=result)
    except Exception:
        db.rollback()
        raise
