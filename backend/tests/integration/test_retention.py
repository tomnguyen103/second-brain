"""raw_text retention TTL (Phase 6, ADR-0012). Asserts on the specific doc created here,
so it is robust to any pre-existing rows in the shared dev DB."""
import os
from datetime import datetime, timedelta, timezone

import pytest

from app.dataops import retention
from app.db.models import AuditLog, Chunk, Document
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB"
)


def _ingest_one(db, embedder, name: str, content: str) -> int:
    r = ingest_documents(
        db, embedder, source=SourceSpec("manual", name),
        documents=[DocumentInput(title="t", content=content)],
    )
    return r.documents[0].document_id


def test_purge_nulls_old_raw_text_keeps_chunks(db_session, fake_embedder):
    doc_id = _ingest_one(db_session, fake_embedder, "RetOld", "alpha beta gamma delta. " * 40)
    doc = db_session.get(Document, doc_id)
    assert doc.raw_text is not None
    chunks_before = db_session.query(Chunk).filter(Chunk.document_id == doc_id).count()
    assert chunks_before >= 1

    # Back-date ingestion well beyond the TTL.
    doc.ingested_at = datetime.now(timezone.utc) - timedelta(days=400)
    db_session.flush()

    purged = retention.purge_raw_text(db_session, older_than_days=180)
    assert purged >= 1

    db_session.refresh(doc)
    assert doc.raw_text is None
    # Chunks (the retrieval units) are untouched.
    assert db_session.query(Chunk).filter(Chunk.document_id == doc_id).count() == chunks_before
    # The purge is audited.
    audited = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "update", AuditLog.entity_type == "document")
        .all()
    )
    assert any(a.detail.get("op") == "retention_purge_raw_text" for a in audited)


def test_recent_doc_not_purged(db_session, fake_embedder):
    doc_id = _ingest_one(db_session, fake_embedder, "RetNew", "fresh content here. " * 40)
    retention.purge_raw_text(db_session, older_than_days=180)
    # A just-ingested doc is younger than the TTL, so its raw_text survives.
    assert db_session.get(Document, doc_id).raw_text is not None
