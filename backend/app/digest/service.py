"""Digest service — backs the MCP send_digest action (ADR-0010).

Composes a markdown digest of recent activity (counts + recently added documents). It composes
only; actual delivery (email/transport) is Phase 5/6. `format_digest` is pure (unit-tested);
`build_digest` queries the DB (integration-tested).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document, Source


@dataclass
class DigestData:
    generated_at: datetime
    n_sources: int
    n_documents: int
    n_chunks: int
    recent_documents: list[tuple[str, str, datetime]] = field(default_factory=list)  # title, source, created


def format_digest(data: DigestData) -> str:
    lines = [
        "# Second Brain — daily digest",
        f"_generated {data.generated_at:%Y-%m-%d %H:%M} UTC_",
        "",
        f"- **{data.n_documents}** documents across **{data.n_sources}** sources "
        f"(**{data.n_chunks}** chunks indexed)",
        "",
        "## Recently added",
    ]
    if not data.recent_documents:
        lines.append("- _nothing yet_")
    else:
        for title, source, created in data.recent_documents:
            lines.append(f"- **{title}** — {source} · {created:%Y-%m-%d}")
    return "\n".join(lines)


def build_digest(db: Session, *, limit: int = 10, now: datetime | None = None) -> str:
    n_sources = db.scalar(select(func.count()).select_from(Source)) or 0
    n_documents = db.scalar(select(func.count()).select_from(Document)) or 0
    n_chunks = db.scalar(select(func.count()).select_from(Chunk)) or 0
    rows = db.execute(
        select(Document.title, Source.name, Document.created_at)
        .join(Source, Source.id == Document.source_id)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .limit(limit)
    ).all()
    data = DigestData(
        generated_at=now or datetime.now(timezone.utc),
        n_sources=n_sources, n_documents=n_documents, n_chunks=n_chunks,
        recent_documents=[(r.title, r.name, r.created_at) for r in rows],
    )
    return format_digest(data)
