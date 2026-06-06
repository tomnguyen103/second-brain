"""REST API coverage for source/document overview."""
from __future__ import annotations

from app import deps
from app.config import Settings
from app.db.models import AuditLog, Chunk, Document, Embedding, Source
from app.main import app

TOKEN = "test-admin-token"
ADMIN = {"X-Second-Brain-Admin-Token": TOKEN}


def _enable_admin():
    app.dependency_overrides[deps.get_settings] = lambda: Settings(
        llm_provider="fake", api_token="test-api-token", admin_token=TOKEN
    )


def _ingest(client, source_name: str) -> int:
    resp = client.post(
        "/ingest",
        json={
            "source": {"type": "manual", "name": source_name, "uri": "file://notes.md"},
            "documents": [
                {
                    "title": "Ops note",
                    "content": "source overview test content " * 40,
                    "content_type": "text/markdown",
                    "tags": ["ops", "rag"],
                }
            ],
        },
    )
    assert resp.status_code == 200
    return resp.json()["source_id"]


def _ingest_many(client, source_name: str, documents: list[dict]) -> int:
    resp = client.post(
        "/ingest",
        json={
            "source": {"type": "manual", "name": source_name, "uri": "file://notes.md"},
            "documents": documents,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["source_id"]


def _first_document_id(client, source_id: int) -> int:
    resp = client.get(f"/sources/{source_id}/documents")
    assert resp.status_code == 200
    return resp.json()["documents"][0]["id"]


def test_sources_api_lists_sources_with_counts(client):
    source_id = _ingest(client, "Source API")

    resp = client.get("/sources")

    assert resp.status_code == 200
    data = resp.json()
    source = next(s for s in data["sources"] if s["id"] == source_id)
    assert source["name"] == "Source API"
    assert source["document_count"] == 1
    assert source["chunk_count"] >= 1


def test_sources_api_lists_documents_for_source(client):
    source_id = _ingest(client, "Document API")

    resp = client.get(f"/sources/{source_id}/documents")

    assert resp.status_code == 200
    data = resp.json()
    assert data["source"]["id"] == source_id
    assert data["total"] == 1
    doc = data["documents"][0]
    assert doc["title"] == "Ops note"
    assert set(doc["tags"]) == {"ops", "rag"}
    assert doc["raw_text_available"] is True


def test_sources_api_missing_source_404(client):
    assert client.get("/sources/99999999/documents").status_code == 404


def test_sources_api_renames_source_and_audits(client, db_session):
    _enable_admin()
    source_id = _ingest(client, "Rename Source")

    resp = client.patch(
        f"/sources/{source_id}",
        json={"name": "Renamed Source"},
        headers=ADMIN,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Renamed Source"
    assert db_session.get(Source, source_id).name == "Renamed Source"
    assert (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "update",
            AuditLog.entity_type == "source",
            AuditLog.entity_id == source_id,
        )
        .count()
        == 1
    )


def test_sources_api_rename_source_requires_admin(client):
    source_id = _ingest(client, "No Admin Rename")

    resp = client.patch(f"/sources/{source_id}", json={"name": "Rejected"})

    assert resp.status_code == 503


def test_sources_api_previews_document_content(client):
    source_id = _ingest(client, "Content Source")
    document_id = _first_document_id(client, source_id)

    resp = client.get(f"/documents/{document_id}/content")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source"]["id"] == source_id
    assert body["document"]["id"] == document_id
    assert body["content_source"] == "raw_text"
    assert "source overview test content" in body["content"]
    assert body["truncated"] is False


def test_sources_api_keeps_preview_route_for_existing_links(client):
    source_id = _ingest(client, "Preview Compatibility Source")
    document_id = _first_document_id(client, source_id)

    resp = client.get(f"/documents/{document_id}/preview")

    assert resp.status_code == 200, resp.text
    assert resp.json()["document"]["id"] == document_id


def test_sources_api_previews_document_chunks_when_raw_text_purged(client, db_session):
    source_id = _ingest(client, "Chunk Content Source")
    document_id = _first_document_id(client, source_id)
    doc = db_session.get(Document, document_id)
    doc.raw_text = None
    db_session.flush()

    resp = client.get(f"/documents/{document_id}/content")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["content_source"] == "chunks"
    assert "source overview test content" in body["content"]


def test_sources_api_renames_document_and_audits(client, db_session):
    _enable_admin()
    source_id = _ingest(client, "Document Rename Source")
    document_id = _first_document_id(client, source_id)

    resp = client.patch(
        f"/documents/{document_id}",
        json={"title": "Renamed document"},
        headers=ADMIN,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "Renamed document"
    assert db_session.get(Document, document_id).title == "Renamed document"
    assert (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "update",
            AuditLog.entity_type == "document",
            AuditLog.entity_id == document_id,
        )
        .count()
        == 1
    )


def test_sources_api_updates_document_content_rebuilds_index_and_audits(client, db_session):
    _enable_admin()
    source_id = _ingest(client, "Document Content Edit Source")
    document_id = _first_document_id(client, source_id)
    old_doc = db_session.get(Document, document_id)
    old_hash = old_doc.content_hash
    old_chunk_ids = [
        c.id for c in db_session.query(Chunk).filter(Chunk.document_id == document_id)
    ]
    assert old_chunk_ids

    edited_content = "edited source content with searchable codex marker. " * 60
    resp = client.patch(
        f"/documents/{document_id}/content",
        json={"content": edited_content},
        headers=ADMIN,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["content_source"] == "raw_text"
    assert body["content"] == edited_content
    assert body["document"]["content_hash"] != old_hash
    assert body["document"]["chunk_count"] >= 1

    db_session.expire_all()
    doc = db_session.get(Document, document_id)
    assert doc.raw_text == edited_content
    assert doc.content_hash == body["document"]["content_hash"]
    assert doc.status == "embedded"

    new_chunk_ids = [
        c.id for c in db_session.query(Chunk).filter(Chunk.document_id == document_id)
    ]
    assert new_chunk_ids
    assert set(new_chunk_ids).isdisjoint(old_chunk_ids)
    assert db_session.query(Embedding).filter(Embedding.chunk_id.in_(old_chunk_ids)).count() == 0
    assert db_session.query(Embedding).filter(Embedding.chunk_id.in_(new_chunk_ids)).count() == len(
        new_chunk_ids
    )
    audit_row = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "update",
            AuditLog.entity_type == "document",
            AuditLog.entity_id == document_id,
        )
        .one()
    )
    assert audit_row.detail["field"] == "content"
    assert audit_row.detail["previous_hash"] == old_hash
    assert audit_row.detail["next_hash"] == body["document"]["content_hash"]


def test_sources_api_update_document_content_rejects_duplicate_hash(client):
    _enable_admin()
    source_id = _ingest_many(
        client,
        "Document Content Duplicate Source",
        [
            {
                "title": "First",
                "content": "first unique source content " * 40,
                "content_type": "text/plain",
            },
            {
                "title": "Second",
                "content": "second duplicate target content " * 40,
                "content_type": "text/plain",
            },
        ],
    )
    resp = client.get(f"/sources/{source_id}/documents")
    assert resp.status_code == 200
    by_title = {doc["title"]: doc["id"] for doc in resp.json()["documents"]}

    resp = client.patch(
        f"/documents/{by_title['First']}/content",
        json={"content": "second duplicate target content " * 40},
        headers=ADMIN,
    )

    assert resp.status_code == 409
    assert "duplicates document" in resp.json()["detail"]


def test_sources_api_deletes_document_cascade_and_audits(client, db_session):
    _enable_admin()
    source_id = _ingest(client, "Document Delete Source")
    document_id = _first_document_id(client, source_id)
    chunk_ids = [c.id for c in db_session.query(Chunk).filter(Chunk.document_id == document_id)]
    assert chunk_ids
    assert db_session.query(Embedding).filter(Embedding.chunk_id.in_(chunk_ids)).count() >= 1

    resp = client.delete(f"/documents/{document_id}", headers=ADMIN)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["document_id"] == document_id
    assert body["source_id"] == source_id
    assert body["chunks_deleted"] == len(chunk_ids)
    assert db_session.query(Source).filter(Source.id == source_id).count() == 1
    assert db_session.query(Document).filter(Document.id == document_id).count() == 0
    assert db_session.query(Chunk).filter(Chunk.document_id == document_id).count() == 0
    assert db_session.query(Embedding).filter(Embedding.chunk_id.in_(chunk_ids)).count() == 0
    assert (
        db_session.query(AuditLog)
        .filter(
            AuditLog.action == "delete",
            AuditLog.entity_type == "document",
            AuditLog.entity_id == document_id,
        )
        .count()
        == 1
    )


def test_sources_api_document_actions_missing_404(client):
    _enable_admin()

    assert client.get("/documents/99999999/content").status_code == 404
    assert client.get("/documents/99999999/preview").status_code == 404
    assert (
        client.patch(
            "/documents/99999999",
            json={"title": "Missing"},
            headers=ADMIN,
        ).status_code
        == 404
    )
    assert (
        client.patch(
            "/documents/99999999/content",
            json={"content": "Missing content"},
            headers=ADMIN,
        ).status_code
        == 404
    )
    assert client.delete("/documents/99999999", headers=ADMIN).status_code == 404
