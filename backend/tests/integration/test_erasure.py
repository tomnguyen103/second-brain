"""GDPR export + delete-my-data at source granularity (Phase 6, ADR-0012).
Post-delete checks use count() queries (which hit the DB) to bypass the ORM identity map."""
import os

import pytest

from app.dataops import erasure
from app.db.models import AuditLog, Chunk, Document, Embedding, Source
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB"
)


def test_export_source_returns_subtree_and_audits(db_session, fake_embedder):
    r = ingest_documents(
        db_session, fake_embedder, source=SourceSpec("manual", "ExportMe"),
        documents=[DocumentInput(title="Doc1", content="export content here. " * 30, tags=["t1"])],
    )
    source_id = r.source_id

    export = erasure.export_source(db_session, source_id)
    assert export["source"]["id"] == source_id
    assert export["source"]["name"] == "ExportMe"
    assert export["document_count"] == 1
    d0 = export["documents"][0]
    assert d0["title"] == "Doc1"
    assert d0["chunk_count"] >= 1
    assert "t1" in d0["tags"]

    assert (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "export",
            AuditLog.entity_type == "source",
            AuditLog.entity_id == source_id,
        )
        .count()
        == 1
    )


def test_delete_source_cascades_and_audits(db_session, fake_embedder):
    r = ingest_documents(
        db_session, fake_embedder, source=SourceSpec("manual", "EraseMe"),
        documents=[DocumentInput(title="d", content="erase this content. " * 30)],
    )
    source_id = r.source_id
    doc_id = r.documents[0].document_id
    chunk_ids = [c.id for c in db_session.query(Chunk).filter(Chunk.document_id == doc_id).all()]
    assert chunk_ids
    assert db_session.query(Embedding).filter(Embedding.chunk_id.in_(chunk_ids)).count() >= 1

    deleted = erasure.delete_source(db_session, source_id)
    assert deleted == 1

    # The whole subtree is gone (count() hits the DB, not the identity map).
    assert db_session.query(Source).filter(Source.id == source_id).count() == 0
    assert db_session.query(Document).filter(Document.id == doc_id).count() == 0
    assert db_session.query(Chunk).filter(Chunk.document_id == doc_id).count() == 0
    assert db_session.query(Embedding).filter(Embedding.chunk_id.in_(chunk_ids)).count() == 0

    assert (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "delete",
            AuditLog.entity_type == "source",
            AuditLog.entity_id == source_id,
        )
        .count()
        == 1
    )


def test_export_missing_source_raises(db_session):
    with pytest.raises(erasure.SourceNotFound):
        erasure.export_source(db_session, 99999999)


def test_delete_missing_source_raises(db_session):
    with pytest.raises(erasure.SourceNotFound):
        erasure.delete_source(db_session, 99999999)
