"""Read-only retrieve→generate for evaluation (ADR-0008).

Mirrors chat.service's pipeline but writes NOTHING to the DB — no conversations, messages, or
retrievals — so running the eval set does not pollute chat history. Returns the rank-ordered
distinct documents retrieved (for retrieval metrics) and the raw answer (for answer metrics).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.chat.prompt import ContextItem, build_messages, get_prompt
from app.config import Settings
from app.retrieval.hybrid import hybrid_search, load_display_chunks


@dataclass
class AnswerResult:
    answer: str
    retrieved_docs: list[str]      # distinct document titles, rank order
    n_context: int                 # number of context items shown to the LLM (= citation range)
    latency_ms: int
    model: str | None


def answer_question(db: Session, embedder, llm, settings: Settings, question: str,
                    *, top_k: int | None = None, source_ids: list[int] | None = None
                    ) -> AnswerResult:
    hits, _meta = hybrid_search(db, embedder, settings, question, top_k=top_k,
                                source_ids=source_ids)
    if not hits:
        # Empty corpus only — with an ingested corpus, vector search always returns candidates,
        # so refusal-on-irrelevance is the LLM's job (measured by the refusal metric).
        return AnswerResult(get_prompt(settings.prompt_version).refusal_text, [], 0, 0, None)

    display = load_display_chunks(db, [h.chunk_id for h in hits])
    seen: set[str] = set()
    retrieved_docs: list[str] = []
    for h in hits:
        title = display[h.chunk_id].document_title
        if title not in seen:
            seen.add(title)
            retrieved_docs.append(title)

    items = [
        ContextItem(i + 1, display[h.chunk_id].source_name,
                    display[h.chunk_id].document_title, display[h.chunk_id].content)
        for i, h in enumerate(hits)
    ]
    messages = build_messages(question, items, prompt_version=settings.prompt_version)

    started = time.perf_counter()
    resp = llm.generate(messages)
    latency_ms = int((time.perf_counter() - started) * 1000)
    return AnswerResult(resp.text, retrieved_docs, len(items), latency_ms, resp.model)
