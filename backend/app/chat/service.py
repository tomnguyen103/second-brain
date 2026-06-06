"""Chat orchestration — retrieve → prompt → generate → persist (ADR-0006/0007)."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chat.prompt import (
    ContextItem,
    all_citation_markers,
    build_messages,
    citation_markers_in_text,
    get_prompt,
    strip_citation_markers,
)
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

_SEGMENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_BLOCK_SPLIT_RE = re.compile(r"\n\s*\n+")
_STRUCTURAL_PREFIX_RE = re.compile(r"^\s*(?:[-*]\s+|\d+[.)]\s*)?")
_SUPPORT_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_'-]{1,}")
_SUPPORT_STOPWORDS = {
    "about", "above", "after", "again", "also", "because", "been", "before", "being",
    "below", "between", "could", "does", "doing", "from", "have", "into", "just",
    "like", "more", "most", "need", "needs", "only", "over", "same", "should",
    "that", "their", "them", "then", "there", "these", "they", "this", "those",
    "through", "using", "very", "what", "when", "where", "which", "while", "with",
    "would", "your", "to",
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


@dataclass
class _CitationValidation:
    cited: list[int]
    invalid_markers: list[int]
    support_failures: list[dict]

    @property
    def failed(self) -> bool:
        return bool(self.invalid_markers or not self.cited or self.support_failures)

    @property
    def reason(self) -> str | None:
        if self.invalid_markers:
            return "invalid_citations"
        if not self.cited:
            return "missing_citations"
        if self.support_failures:
            return "unsupported_claims"
        return None


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


def _claim_blocks(answer: str) -> list[str]:
    return [block.strip() for block in _BLOCK_SPLIT_RE.split(answer or "") if block.strip()]


def _is_structural_segment(segment: str) -> bool:
    text = strip_citation_markers(segment)
    text = _STRUCTURAL_PREFIX_RE.sub("", text).strip(" \t-*`_")
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text).strip()
    if not text or not text.endswith(":"):
        return False
    return len(_support_tokens(text)) <= 12


def _context_tokens(prepared: _PreparedChat, marker: int) -> set[str]:
    hit = prepared.hits[marker - 1]
    dc = prepared.display[hit.chunk_id]
    return _support_tokens(f"{dc.source_name} {dc.document_title} {dc.content}")


def _has_non_ascii_letters(text: str) -> bool:
    return any(ch.isalpha() and not ch.isascii() for ch in text or "")


def _cited_context_is_cross_lingual(prepared: _PreparedChat, markers: list[int]) -> bool:
    for marker in markers:
        hit = prepared.hits[marker - 1]
        dc = prepared.display[hit.chunk_id]
        if _has_non_ascii_letters(dc.content):
            return True
    return False


def _citation_support_failures(answer: str, prepared: _PreparedChat) -> list[dict]:
    """Return answer segments whose cited marker does not plausibly support the claim.

    This is a conservative lexical guard, not a semantic verifier. It blocks obvious prompt
    injection/hallucination where a valid marker is pasted onto unrelated text.
    """
    failures: list[dict] = []
    for block in _claim_blocks(answer):
        block_markers = [
            marker for marker in citation_markers_in_text(block)
            if 1 <= marker <= prepared.item_count
        ]
        for segment in _claim_segments(block):
            direct_markers = [
                marker for marker in citation_markers_in_text(segment)
                if 1 <= marker <= prepared.item_count
            ]
            markers = direct_markers or block_markers
            claim_text = strip_citation_markers(segment)
            claim_tokens = _support_tokens(claim_text)
            if not claim_tokens:
                continue
            if _is_structural_segment(segment):
                continue
            if not markers:
                failures.append({"reason": "missing_segment_citation", "segment": segment[:160]})
                continue

            cited_tokens: set[str] = set()
            for marker in markers:
                cited_tokens.update(_context_tokens(prepared, marker))
            overlap = claim_tokens & cited_tokens
            min_overlap = 1 if len(claim_tokens) <= 4 else 2
            if len(overlap) < min_overlap and _cited_context_is_cross_lingual(
                prepared,
                markers,
            ):
                continue
            if len(overlap) < min_overlap:
                failures.append({
                    "reason": "unsupported_segment",
                    "segment": segment[:160],
                    "markers": markers,
                    "overlap": sorted(overlap)[:10],
                })
    return failures


def _validate_citations(answer: str, prepared: _PreparedChat) -> _CitationValidation:
    emitted_markers = all_citation_markers(answer)
    invalid_markers = [i for i in emitted_markers if i < 1 or i > prepared.item_count]
    cited = [i for i in emitted_markers if 1 <= i <= prepared.item_count]
    support_failures = (
        [] if invalid_markers or not cited else _citation_support_failures(answer, prepared)
    )
    return _CitationValidation(cited, invalid_markers, support_failures)


def _repair_citation_messages(
    prepared: _PreparedChat,
    draft: str,
    validation: _CitationValidation,
) -> list[LLMMessage]:
    failed_segments = [
        item.get("segment", "")
        for item in validation.support_failures[:8]
        if item.get("segment")
    ]
    failed_block = ""
    if validation.invalid_markers:
        failed_block += (
            "Invalid citation markers: "
            f"{', '.join(str(i) for i in validation.invalid_markers)}\n"
        )
    if failed_segments:
        failed_block += "Segments that failed validation:\n" + "\n".join(
            f"- {segment}" for segment in failed_segments
        )
    if not failed_block:
        failed_block = "The draft did not include valid citations."

    return [
        *prepared.messages,
        LLMMessage(
            "user",
            "Your previous draft failed citation validation. Rewrite it using ONLY the "
            "numbered context above.\n\n"
            "Rules:\n"
            "- Every factual sentence must include bracket citations in that same sentence.\n"
            "- Do not write uncited headings, preambles, markdown labels, or transitions.\n"
            "- Remove claims that are not directly supported by the numbered context.\n"
            "- If the context is not in English, either keep source-language terms in the "
            "same cited sentence or remove translated claims that cannot be grounded.\n"
            "- Return only the rewritten answer.\n\n"
            f"{failed_block}\n\n"
            f"Draft to repair:\n{draft}",
        ),
    ]


def _merge_usage(base: dict, extra: dict) -> dict:
    merged = dict(base or {})
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        left = merged.get(key)
        right = (extra or {}).get(key)
        if isinstance(left, int) and isinstance(right, int):
            merged[key] = left + right
        elif left is None:
            merged[key] = right
    return merged


def _repair_citations_if_needed(
    llm,
    prepared: _PreparedChat,
    *,
    answer: str,
    model: str | None,
    usage: dict,
    latency_ms: int,
) -> tuple[str, str | None, dict, int]:
    validation = _validate_citations(answer, prepared)
    if not validation.failed:
        return answer, model, usage, latency_ms

    prepared.meta = {
        **prepared.meta,
        "citation_repair_attempted": True,
        "citation_repair_original_reason": validation.reason,
    }
    try:
        started = time.perf_counter()
        repaired = llm.generate(_repair_citation_messages(prepared, answer, validation))
        repair_latency_ms = int((time.perf_counter() - started) * 1000)
    except Exception:  # pragma: no cover - provider/network specific
        prepared.meta = {
            **prepared.meta,
            "citation_repair_succeeded": False,
            "citation_repair_error": "provider_error",
        }
        return answer, model, usage, latency_ms

    repaired_usage = {
        "prompt_tokens": repaired.prompt_tokens,
        "completion_tokens": repaired.completion_tokens,
        "total_tokens": repaired.total_tokens,
    }
    repaired_validation = _validate_citations(repaired.text, prepared)
    prepared.meta = {
        **prepared.meta,
        "citation_repair_succeeded": not repaired_validation.failed,
        "citation_repair_latency_ms": repair_latency_ms,
    }
    if repaired_validation.failed:
        prepared.meta = {
            **prepared.meta,
            "citation_repair_failure_reason": repaired_validation.reason,
        }
        return answer, model, _merge_usage(usage, repaired_usage), latency_ms + repair_latency_ms

    return (
        repaired.text,
        repaired.model or model,
        _merge_usage(usage, repaired_usage),
        latency_ms + repair_latency_ms,
    )


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
    validation = _validate_citations(answer, prepared)
    cited = validation.cited
    if validation.failed:
        answer = CITATION_FAILURE_TEXT
        prepared.meta = {
            **prepared.meta,
            "citation_validation_failed": True,
            "citation_failure_reason": validation.reason,
            "invalid_citation_markers": validation.invalid_markers,
            "unsupported_citation_segments": validation.support_failures,
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
    answer, model, usage, latency_ms = _repair_citations_if_needed(
        llm,
        prepared,
        answer=resp.text,
        model=resp.model,
        usage=usage,
        latency_ms=latency_ms,
    )
    return _finalize_chat(db, prepared, answer=answer, model=model,
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
        streamed_answer = "".join(parts)
        final_answer, model, usage, latency_ms = _repair_citations_if_needed(
            llm,
            prepared,
            answer=streamed_answer,
            model=model,
            usage=usage,
            latency_ms=latency_ms,
        )
        result = _finalize_chat(db, prepared, answer=final_answer, model=model,
                                usage=usage, latency_ms=latency_ms)
        # Retrieved notes are untrusted input. Do not send provider chunks until the
        # assembled answer passes citation validation, otherwise prompt-injected text
        # could leak over SSE before the final response is replaced.
        if (
            not result.retrieval.get("citation_validation_failed")
            and result.answer == streamed_answer
        ):
            for text in delta_parts:
                yield ChatStreamEvent(type="delta", text=text)
        yield ChatStreamEvent(type="complete", result=result)
    except Exception:
        db.rollback()
        raise
