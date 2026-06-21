import os
import pytest
from sqlalchemy import select

from app.db.models import Document
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from tests.helpers import sample_pdf_bytes

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB")

def test_ingest_creates_rows_and_dedupes(db_session, fake_embedder):
    spec = SourceSpec(type="manual", name="T")
    docs = [DocumentInput(title="A", content="alpha beta. " * 50, tags=["x"])]
    r1 = ingest_documents(db_session, fake_embedder, source=spec, documents=docs)
    assert r1.documents[0].status == "embedded"
    assert r1.documents[0].chunk_count >= 1
    assert r1.documents[0].embedded_count == r1.documents[0].chunk_count

    r2 = ingest_documents(db_session, fake_embedder, source=spec, documents=docs)
    assert r2.documents[0].status == "duplicate"
    assert r2.source_id == r1.source_id            # source reused


def test_partial_failure_isolates_bad_doc(db_session, fake_embedder):
    """A bad doc in a batch must not prevent good docs from being stored."""
    class _BrokenEmbedder:
        model_name = fake_embedder.model_name
        dim = fake_embedder.dim
        call_count = 0

        def encode(self, texts):
            self.call_count += 1
            if self.call_count > 1:
                raise RuntimeError("embed failure")
            return fake_embedder.encode(texts)

        def count_tokens(self, text):
            return fake_embedder.count_tokens(text)

    bad_embedder = _BrokenEmbedder()
    spec = SourceSpec(type="manual", name="partial")
    docs = [
        DocumentInput(title="Good", content="good content " * 10),
        DocumentInput(title="Bad",  content="bad content " * 10),
    ]
    result = ingest_documents(db_session, bad_embedder, source=spec, documents=docs)
    statuses = {d.title: d.status for d in result.documents}
    assert statuses["Good"] == "embedded"
    assert statuses["Bad"] == "failed"


def test_ingest_fails_doc_when_embedding_count_mismatches(db_session, fake_embedder):
    class _ShortEmbedder:
        model_name = fake_embedder.model_name
        dim = fake_embedder.dim

        def encode(self, texts):
            vectors = fake_embedder.encode(texts)
            return vectors[:-1]

        def count_tokens(self, text):
            return fake_embedder.count_tokens(text)

    spec = SourceSpec(type="manual", name="mismatched embeddings")
    docs = [
        DocumentInput(
            title="Mismatch",
            content=("alpha beta gamma delta epsilon zeta eta theta iota kappa. " * 80),
        )
    ]

    result = ingest_documents(db_session, _ShortEmbedder(), source=spec, documents=docs)

    assert result.documents[0].status == "failed"
    assert "unexpected vector count" in (result.documents[0].error or "")
    stored = db_session.scalar(select(Document).where(Document.title == "Mismatch"))
    assert stored is None


def test_ingest_upload_text_files(client):
    response = client.post(
        "/ingest/upload",
        data={
            "source_name": "Uploaded Notes",
            "source_type": "file_upload",
            "tags": "uploads, rag",
        },
        files=[
            ("files", ("notes.md", b"# Upload\n\nFile upload content " * 20, "text/markdown")),
            ("files", ("plain.txt", b"Plain upload content " * 20, "text/plain")),
        ],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"]["embedded"] == 2
    assert [doc["status"] for doc in body["documents"]] == ["embedded", "embedded"]

    docs = client.get(f"/sources/{body['source_id']}/documents")
    assert docs.status_code == 200, docs.text
    listed = docs.json()
    assert listed["source"]["type"] == "file_upload"
    assert listed["total"] == 2
    assert {doc["content_type"] for doc in listed["documents"]} == {
        "text/markdown",
        "text/plain",
    }
    assert {tag for doc in listed["documents"] for tag in doc["tags"]} == {"uploads", "rag"}


def test_ingest_upload_pdf_uses_pdf_source_type(client):
    response = client.post(
        "/ingest/upload",
        data={"source_name": "Uploaded PDF", "source_type": "pdf_upload"},
        files=[("files", ("paper.pdf", sample_pdf_bytes(), "application/pdf"))],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"]["embedded"] == 1
    assert body["documents"][0]["title"] == "paper"

    docs = client.get(f"/sources/{body['source_id']}/documents")
    assert docs.status_code == 200, docs.text
    listed = docs.json()
    assert listed["source"]["type"] == "pdf_upload"
    assert listed["documents"][0]["content_type"] == "application/pdf"


def test_ingest_upload_rejects_unsupported_file_type(client):
    response = client.post(
        "/ingest/upload",
        data={"source_name": "Bad Uploads", "source_type": "file_upload"},
        files=[("files", ("payload.exe", b"MZ fake executable", "application/octet-stream"))],
    )

    assert response.status_code == 400
    assert "unsupported file type" in response.json()["detail"]


def test_ingest_upload_rejects_pdf_source_type_for_mixed_files(client):
    response = client.post(
        "/ingest/upload",
        data={"source_name": "Mixed Uploads", "source_type": "pdf_upload"},
        files=[
            ("files", ("paper.pdf", sample_pdf_bytes(), "application/pdf")),
            ("files", ("notes.txt", b"Not a PDF", "text/plain")),
        ],
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "source_type pdf_upload only accepts PDF files"
