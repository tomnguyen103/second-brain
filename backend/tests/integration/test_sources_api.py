"""REST API coverage for source/document overview."""
from __future__ import annotations


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
