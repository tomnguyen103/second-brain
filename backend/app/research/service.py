"""Research service — the MCP research_topic action (ADR-0010).

The flagship agentic action: the LLM researches a topic, the summary is stored as a
`research_note` source and run through the normal ingest pipeline (chunk + embed), so the result
is permanently searchable. Inline + synchronous (matches ADR-0007); the `fake` driver yields a
deterministic note for tests. `build_research_messages` is pure (unit-tested); `research_topic`
is integration-tested (stores + embeds + becomes searchable).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.llm.base import LLMMessage
from app.security import ensure_no_sensitive_content

# All automated research notes live under one source so they're easy to find and filter.
RESEARCH_SOURCE = "Automated Research"

RESEARCH_SYSTEM = (
    "You are a research assistant. Given a topic, write a concise, factual research note: a one "
    "or two sentence overview followed by 3–6 key points as bullet markers. Be neutral and "
    "specific. If the topic is ambiguous, state the most common interpretation. Do not fabricate "
    "citations, statistics, or sources."
)


def build_research_messages(topic: str) -> list[LLMMessage]:
    topic = (topic or "").strip()
    return [
        LLMMessage("system", RESEARCH_SYSTEM),
        LLMMessage("user", f"Research this topic and write a research note:\n\n{topic}"),
    ]


@dataclass
class ResearchResult:
    topic: str
    document_id: int | None
    source_id: int
    status: str                  # embedded | duplicate | failed
    duplicate_of: int | None
    chunk_count: int
    model: str | None
    summary: str
    searchable: bool


def research_topic(db: Session, embedder, llm, topic: str) -> ResearchResult:
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("research topic is required")
    ensure_no_sensitive_content(topic, context="research topic")

    resp = llm.generate(build_research_messages(topic))
    summary = resp.text or ""
    ensure_no_sensitive_content(summary, context="research summary")

    result = ingest_documents(
        db, embedder,
        source=SourceSpec(type="research_note", name=RESEARCH_SOURCE),
        documents=[DocumentInput(
            title=topic, content=summary, content_type="text/markdown",
            metadata={"kind": "research", "topic": topic, "model": resp.model},
        )],
    )
    doc = result.documents[0]
    return ResearchResult(
        topic=topic, document_id=doc.document_id, source_id=result.source_id,
        status=doc.status, duplicate_of=doc.duplicate_of, chunk_count=doc.chunk_count,
        model=resp.model, summary=summary,
        searchable=doc.status in ("embedded", "duplicate"),
    )
