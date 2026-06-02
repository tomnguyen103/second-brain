import os
import pytest
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents

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
