"""Job handler registry (Phase 5, ADR-0013).

Maps a job ``type`` to a handler ``handler(db, payload, *, embedder, llm) -> dict | None``.
Production handlers (``briefing``, ``research``) register themselves when this module is
imported (added in Tasks 5/6), so importing ``app.jobs.handlers`` populates the registry for
the worker. Tests inject their own dict into ``run_once(..., handlers=...)`` instead of
mutating the global, and use ``register``/``unregister`` for the registry itself.
"""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.briefing.service import build_briefing
from app.db.models import Briefing
from app.research.service import research_topic

# type -> handler(db, payload, *, embedder, llm) -> dict | None
HANDLERS: dict[str, Callable] = {}


def register(job_type: str, handler: Callable) -> Callable:
    """Register (or replace) the handler for a job type. Returns the handler."""
    HANDLERS[job_type] = handler
    return handler


def unregister(job_type: str) -> None:
    """Remove a handler if present (used by tests to clean up)."""
    HANDLERS.pop(job_type, None)


def handle_briefing(db: Session, payload: dict, *, embedder, llm) -> dict:
    """`briefing` job: summarize documents added since the last briefing's `period_end`
    (or, with no prior briefing, the lookback window) and store a new Briefing."""
    since = db.scalar(select(Briefing.period_end).order_by(Briefing.id.desc()).limit(1))
    briefing = build_briefing(db, llm, since=since)
    return {"briefing_id": briefing.id, "document_count": briefing.document_count}


register("briefing", handle_briefing)


def handle_research(db: Session, payload: dict, *, embedder, llm) -> dict:
    """`research` job: research a topic and file the note back into the brain — the async
    path for ADR-0010's research_topic (closes the Phase-5 deferral). The inline MCP path
    stays; this is the queued one. Returns a JSON-able summary of what was stored."""
    res = research_topic(db, embedder, llm, (payload or {}).get("topic", ""))
    return {
        "topic": res.topic,
        "document_id": res.document_id,
        "source_id": res.source_id,
        "status": res.status,
        "chunk_count": res.chunk_count,
        "searchable": res.searchable,
    }


register("research", handle_research)
