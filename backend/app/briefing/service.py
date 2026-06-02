"""Briefing service (Phase 5, ADR-0013).

Summarizes the documents ingested in a time window into a stored morning briefing. The two
pure functions (`build_briefing_messages`, `format_briefing`) are unit-tested DB-free;
`build_briefing` queries Postgres + the LLMClient and persists a `Briefing` (integration-tested).

Mirrors two existing seams: it reuses the digest's markdown shape (`app.digest.service`) and the
chat zero-context short-circuit — an empty window produces a valid "nothing new" briefing with
**no LLM call** (and `model=None`).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Briefing, Document, Source
from app.llm.base import LLMMessage

# title, source name, created_at
DocRow = tuple[str, str, datetime]

BRIEFING_SYSTEM = (
    "You are my morning briefing assistant. Given the list of documents newly added to my "
    "knowledge base since the last briefing, write a short, friendly briefing (2-4 sentences) "
    "that tells me what's new and why it might matter. Group related items. Be concise and "
    "specific; do not invent documents or facts beyond the titles given."
)

NOTHING_NEW = "Nothing new since the last briefing."


def build_briefing_messages(
    period_start: datetime, period_end: datetime, docs: list[DocRow]
) -> list[LLMMessage]:
    """Build the LLM prompt summarizing `docs` added in (period_start, period_end]. Pure."""
    doc_lines = "\n".join(f"- {title} ({source})" for title, source, _created in docs)
    user = (
        f"Documents added between {period_start:%Y-%m-%d %H:%M} and "
        f"{period_end:%Y-%m-%d %H:%M} UTC.\n\n"
        f"New documents ({len(docs)}):\n{doc_lines}\n\n"
        "Write my briefing."
    )
    return [LLMMessage("system", BRIEFING_SYSTEM), LLMMessage("user", user)]


def format_briefing(
    summary: str,
    period_start: datetime,
    period_end: datetime,
    docs: list[DocRow],
    *,
    generated_at: datetime,
) -> str:
    """Compose the stored markdown body from the summary + the new-document list. Pure."""
    lines = [
        "# Second Brain — morning briefing",
        f"_generated {generated_at:%Y-%m-%d %H:%M} UTC · {len(docs)} new since "
        f"{period_start:%Y-%m-%d %H:%M}_",
        "",
        summary.strip(),
        "",
        "## New since last briefing",
    ]
    if not docs:
        lines.append("- _nothing new_")
    else:
        for title, source, created in docs:
            lines.append(f"- **{title}** — {source} · {created:%Y-%m-%d}")
    return "\n".join(lines)


def build_briefing(
    db: Session,
    llm,
    *,
    since: datetime | None = None,
    now: datetime | None = None,
) -> Briefing:
    """Summarize documents ingested in (since, now] and persist a `Briefing`.

    `since` defaults to `now - briefing_lookback_hours` (the first-ever briefing has no prior
    period_end). An empty window short-circuits to a "nothing new" briefing with no LLM call
    and `model=None`, mirroring the chat zero-context rule. Flushes (the caller commits).
    """
    now = now or datetime.now(timezone.utc)
    if since is None:
        since = now - timedelta(hours=settings.briefing_lookback_hours)

    rows = db.execute(
        select(Document.title, Source.name, Document.created_at)
        .join(Source, Source.id == Document.source_id)
        .where(Document.created_at > since, Document.created_at <= now)
        .order_by(Document.created_at.asc(), Document.id.asc())
    ).all()
    docs: list[DocRow] = [(r.title, r.name, r.created_at) for r in rows]

    if docs:
        resp = llm.generate(build_briefing_messages(since, now, docs))
        summary = (resp.text or "").strip()
        model = resp.model
    else:
        summary = NOTHING_NEW
        model = None

    briefing = Briefing(
        generated_at=now,
        period_start=since,
        period_end=now,
        summary=summary,
        body_markdown=format_briefing(summary, since, now, docs, generated_at=now),
        document_count=len(docs),
        model=model,
    )
    db.add(briefing)
    db.flush()
    db.refresh(briefing)
    return briefing
