import os
import pytest
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB")


def _sample_pdf_bytes() -> bytes:
    content = b"BT /F1 24 Tf 72 720 Td (Upload PDF content) Tj ET\n"
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
        ),
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        (
            f"5 0 obj\n<< /Length {len(content)} >>\nstream\n".encode("ascii")
            + content
            + b"endstream\nendobj\n"
        ),
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


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
        files=[("files", ("paper.pdf", _sample_pdf_bytes(), "application/pdf"))],
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
            ("files", ("paper.pdf", _sample_pdf_bytes(), "application/pdf")),
            ("files", ("notes.txt", b"Not a PDF", "text/plain")),
        ],
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "source_type pdf_upload only accepts PDF files"
