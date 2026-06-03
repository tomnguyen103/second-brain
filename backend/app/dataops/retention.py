"""raw_text retention (ADR-0012, D4).

After a document is embedded, its chunks + embeddings carry the retrievable signal — the
original `raw_text` is the only PII-bearing free text we keep, and per the retention policy it
is nulled `retention_raw_text_days` after ingestion. Chunks and embeddings are NOT removed
(that would break search); retention != erasure (see erasure.py for delete-my-data).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.dataops import audit
from app.db.models import Document


def _cutoff(older_than_days: int) -> datetime:
    if older_than_days < 1:
        raise ValueError("older_than_days must be at least 1")
    return datetime.now(timezone.utc) - timedelta(days=older_than_days)


def count_purge_candidates(db: Session, *, older_than_days: int) -> int:
    """Return how many embedded documents would have raw_text nulled."""
    cutoff = _cutoff(older_than_days)
    return db.scalar(
        select(func.count(Document.id)).where(
            Document.status == "embedded",
            Document.raw_text.is_not(None),
            Document.ingested_at.is_not(None),
            Document.ingested_at < cutoff,
        )
    ) or 0


def purge_raw_text(
    db: Session,
    *,
    older_than_days: int,
    actor: str = "retention-job",
    audit_enabled: bool = True,
) -> int:
    """Null `raw_text` for embedded documents ingested more than `older_than_days` ago.

    Returns the number of documents purged. Does not commit — the caller owns the txn.
    """
    cutoff = _cutoff(older_than_days)
    stmt = (
        update(Document)
        .where(
            Document.status == "embedded",
            Document.raw_text.is_not(None),
            Document.ingested_at.is_not(None),
            Document.ingested_at < cutoff,
        )
        .values(raw_text=None)
    )
    result = db.execute(stmt, execution_options={"synchronize_session": False})
    purged = result.rowcount or 0
    if purged:
        audit.record(
            db,
            actor=actor,
            action="update",
            entity_type="document",
            detail={
                "op": "retention_purge_raw_text",
                "older_than_days": older_than_days,
                "purged": purged,
            },
            enabled=audit_enabled,
        )
    db.flush()
    return purged
