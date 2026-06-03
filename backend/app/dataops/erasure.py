"""GDPR data-subject actions on a source (ADR-0012, D5).

A `source` is the unit the user added (a notes folder, an upload, a research note), so it is
the natural granularity for the "right to access" (export) and "right to erasure" (delete).
Deleting a source cascades to its documents → chunks → embeddings via the FK `ON DELETE
CASCADE` declared in the baseline migration — we issue a Core DELETE so the database enforces
the cascade (rather than the ORM trying to NULL the NOT NULL `documents.source_id`). Both
actions write an audit row.
"""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.dataops import audit
from app.db.models import Chunk, Document, Source
from app.security import redact_sensitive_text, redact_sensitive_value


class SourceNotFound(Exception):
    """Raised when an export/delete targets a source id that does not exist."""


def export_source(
    db: Session,
    source_id: int,
    *,
    actor: str = "data-subject",
    audit_enabled: bool = True,
) -> dict:
    """Return the source and its documents (with chunk counts) as a JSON-able dict.

    Audited as an `export`. Does not commit — the caller owns the txn.
    """
    src = db.get(Source, source_id)
    if src is None:
        raise SourceNotFound(f"source {source_id} not found")

    docs = db.scalars(select(Document).where(Document.source_id == source_id)).all()
    documents = []
    for d in docs:
        chunk_count = db.scalar(select(func.count(Chunk.id)).where(Chunk.document_id == d.id))
        documents.append(
            {
                "id": d.id,
                "title": redact_sensitive_text(d.title),
                "content_type": d.content_type,
                "content_hash": d.content_hash,
                "status": d.status,
                "raw_text": redact_sensitive_text(d.raw_text) if d.raw_text else None,
                "metadata": redact_sensitive_value(d.metadata_),
                "tags": [t.name for t in d.tags],
                "chunk_count": chunk_count,
                "ingested_at": d.ingested_at.isoformat() if d.ingested_at else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
        )

    export = {
        "source": {
            "id": src.id,
            "type": src.type,
            "name": redact_sensitive_text(src.name),
            "uri": redact_sensitive_text(src.uri) if src.uri else None,
            "config": redact_sensitive_value(src.config),
            "created_at": src.created_at.isoformat() if src.created_at else None,
        },
        "documents": documents,
        "document_count": len(documents),
    }
    audit.record(
        db,
        actor=actor,
        action="export",
        entity_type="source",
        entity_id=source_id,
        detail={"document_count": len(documents)},
        enabled=audit_enabled,
    )
    db.flush()
    return export


def preview_delete_source(db: Session, source_id: int) -> dict:
    """Return a delete preview used by the API confirmation gate."""
    src = db.get(Source, source_id)
    if src is None:
        raise SourceNotFound(f"source {source_id} not found")
    doc_count = db.scalar(
        select(func.count(Document.id)).where(Document.source_id == source_id)
    ) or 0
    return {
        "source_id": src.id,
        "source_type": src.type,
        "source_name": redact_sensitive_text(src.name),
        "documents_deleted": doc_count,
        "confirmation_required": "resubmit with confirm_source_name set to the exact source name",
    }


def delete_source(
    db: Session,
    source_id: int,
    *,
    actor: str = "data-subject",
    audit_enabled: bool = True,
) -> int:
    """Delete a source (cascading to documents → chunks → embeddings). Returns the document
    count removed. Audited as a `delete`. Does not commit — the caller owns the txn.
    """
    exists = db.scalar(select(Source.id).where(Source.id == source_id))
    if exists is None:
        raise SourceNotFound(f"source {source_id} not found")

    doc_count = db.scalar(
        select(func.count(Document.id)).where(Document.source_id == source_id)
    )
    db.execute(
        delete(Source).where(Source.id == source_id),
        execution_options={"synchronize_session": False},
    )
    audit.record(
        db,
        actor=actor,
        action="delete",
        entity_type="source",
        entity_id=source_id,
        detail={"documents_deleted": doc_count},
        enabled=audit_enabled,
    )
    db.flush()
    return doc_count
