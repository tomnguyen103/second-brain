"""REST API coverage for the local operator status endpoint."""
from __future__ import annotations

from app.ingest.service import DocumentInput, SourceSpec, ingest_documents


def test_status_api_reports_runtime_db_worker_and_knowledge(client, db_session, fake_embedder):
    ingest_documents(
        db_session,
        fake_embedder,
        source=SourceSpec(type="manual", name="Status API"),
        documents=[
            DocumentInput(
                title="Status note",
                content="local status panel source count and worker queue " * 30,
            )
        ],
    )

    resp = client.get("/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["database"]["reachable"] is True
    assert data["database"]["migration_current"]
    assert data["database"]["migration_head"]
    assert data["database"]["migrated"] is True
    assert data["knowledge"]["source_count"] >= 1
    assert data["knowledge"]["document_count"] >= 1
    assert data["knowledge"]["chunk_count"] >= 1
    assert data["worker"]["status"] in {"idle", "active", "pending", "attention"}
    assert data["runtime"]["llm_provider"] == "fake"
