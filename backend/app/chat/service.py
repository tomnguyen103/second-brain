"""Chat orchestration — retrieve → prompt → generate → persist (ADR-0006/0007)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chat.prompt import ContextItem, build_messages, get_prompt, parse_citations
from app.config import Settings
from app.db.models import Conversation, Message, Retrieval
from app.llm.base import LLMMessage
from app.retrieval.hybrid import hybrid_search, load_display_chunks


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


def _history(db: Session, conversation_id: int, window: int) -> list[LLMMessage]:
    rows = db.scalars(
        select(Message).where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc()).limit(window)).all()
    return [LLMMessage(m.role, m.content) for m in reversed(rows)]


def chat(db: Session, embedder, llm, settings: Settings, *, message: str,
         conversation_id: int | None = None, top_k: int | None = None,
         filters: dict | None = None, include_chunks: bool = True) -> ChatResult:
    filters = filters or {}
    if conversation_id is None:
        conv = Conversation(title=message[:80])
        db.add(conv)
        db.flush()
        conversation_id = conv.id

    history = _history(db, conversation_id, settings.history_window)
    db.add(Message(conversation_id=conversation_id, role="user", content=message))
    db.flush()

    hits, meta = hybrid_search(db, embedder, settings, message,
                               top_k=top_k, source_ids=filters.get("source_ids"),
                               tags=filters.get("tags"))

    # Zero-context short-circuit — no LLM call (ADR-0006). Refusal text follows the active
    # prompt version (ADR-0009) so an A/B variant can phrase its refusal differently.
    if not hits:
        refusal = get_prompt(settings.prompt_version).refusal_text
        assistant = Message(conversation_id=conversation_id, role="assistant",
                            content=refusal, model=None)
        db.add(assistant)
        db.commit()
        return ChatResult(conversation_id, assistant.id, refusal, [],
                          {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                          None, 0, {**meta, "fused_returned": 0})

    display = load_display_chunks(db, [h.chunk_id for h in hits])
    items = [ContextItem(i + 1, display[h.chunk_id].source_name,
                         display[h.chunk_id].document_title, display[h.chunk_id].content)
             for i, h in enumerate(hits)]
    messages = build_messages(message, items, history, prompt_version=settings.prompt_version)

    started = time.perf_counter()
    resp = llm.generate(messages)
    latency_ms = int((time.perf_counter() - started) * 1000)

    cited = parse_citations(resp.text, len(items))
    usage = {"prompt_tokens": resp.prompt_tokens, "completion_tokens": resp.completion_tokens,
             "total_tokens": resp.total_tokens}
    assistant = Message(conversation_id=conversation_id, role="assistant", content=resp.text,
                        model=resp.model, token_usage=usage, latency_ms=latency_ms)
    db.add(assistant)
    db.flush()

    citations: list[Citation] = []
    for i, h in enumerate(hits):
        marker = i + 1
        db.add(Retrieval(message_id=assistant.id, chunk_id=h.chunk_id, rank=h.rank,
                         score=h.score, vector_score=h.vector_score,
                         fulltext_score=h.fulltext_score, method=h.method))
        if marker in cited:
            dc = display[h.chunk_id]
            citations.append(Citation(
                marker=marker, chunk_id=h.chunk_id, document_id=dc.document_id,
                document_title=dc.document_title, source_id=dc.source_id,
                source_name=dc.source_name, score=h.score, vector_score=h.vector_score,
                fulltext_score=h.fulltext_score, method=h.method,
                snippet=dc.content if include_chunks else None,
                char_start=dc.char_start if include_chunks else None,
                char_end=dc.char_end if include_chunks else None))

    db.commit()
    return ChatResult(conversation_id, assistant.id, resp.text, citations, usage,
                      resp.model, latency_ms, meta)
