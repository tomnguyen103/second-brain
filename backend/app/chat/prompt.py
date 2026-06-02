"""Prompt template + citation parsing — ADR-0006."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.llm.base import LLMMessage

PROMPT_VERSION = "rag-v1"
REFUSAL_TEXT = "I don't have anything in your notes about that yet."
SYSTEM_PROMPT = (
    "You are Second Brain, a personal assistant. Answer ONLY using the numbered context "
    "below. Cite every claim with bracketed markers like [1], [2] that refer to the context "
    "items you used. If the context does not contain the answer, say so plainly. Never invent "
    "facts or citations that are not in the context."
)

_MARKER = re.compile(r"\[(\d+)\]")


@dataclass
class ContextItem:
    marker: int                 # 1-based
    source_name: str
    document_title: str
    content: str


def build_context_block(items: list[ContextItem]) -> str:
    return "\n\n".join(
        f"[{it.marker}] (source: {it.source_name} · doc: {it.document_title})\n{it.content}"
        for it in items
    )


def build_messages(question: str, items: list[ContextItem],
                   history: list[LLMMessage] | None = None) -> list[LLMMessage]:
    msgs = [LLMMessage("system", SYSTEM_PROMPT)]
    msgs += history or []
    block = build_context_block(items)
    msgs.append(LLMMessage("user", f"Context:\n{block}\n\nQuestion: {question}"))
    return msgs


def parse_citations(answer: str, n_items: int) -> list[int]:
    """Ordered, de-duplicated, in-range markers the model actually used."""
    seen: list[int] = []
    for m in _MARKER.findall(answer):
        i = int(m)
        if 1 <= i <= n_items and i not in seen:
            seen.append(i)
    return seen
