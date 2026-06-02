import os
import pytest
from app.config import Settings
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.retrieval.hybrid import hybrid_search, load_display_chunks

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB")


def test_hybrid_search_returns_results_and_meta(db_session, fake_embedder):
    spec = SourceSpec(type="manual", name="retrieval-test")
    ingest_documents(db_session, fake_embedder, source=spec, documents=[
        DocumentInput(title="HNSW doc", content="HNSW tuning parameters m ef_construction. " * 15),
        DocumentInput(title="Unrelated", content="completely unrelated topic about cooking. " * 15),
    ])

    settings = Settings()
    hits, meta = hybrid_search(db_session, fake_embedder, settings, "HNSW tuning")

    assert len(hits) >= 1
    assert meta["fused_returned"] == len(hits)
    assert meta["candidates_vector"] >= 1 or meta["candidates_fulltext"] >= 1

    # load_display_chunks returns the content for each hit
    display = load_display_chunks(db_session, [h.chunk_id for h in hits])
    assert len(display) == len(hits)
    for h in hits:
        dc = display[h.chunk_id]
        assert dc.content
        assert dc.document_title in ("HNSW doc", "Unrelated")


def test_hybrid_search_fulltext_finds_exact_term(db_session, fake_embedder):
    spec = SourceSpec(type="manual", name="fts-test")
    ingest_documents(db_session, fake_embedder, source=spec, documents=[
        DocumentInput(title="Rare term doc",
                      content="xyzquux is a very rare token that only appears here. " * 10),
    ])

    settings = Settings()
    hits, meta = hybrid_search(db_session, fake_embedder, settings, "xyzquux")
    assert meta["candidates_fulltext"] >= 1
    assert any(h.method in ("fulltext", "hybrid") for h in hits)
