import os
import pytest
from app.config import Settings
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.retrieval.hybrid import hybrid_search, load_display_chunks

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB")


def test_hybrid_search_returns_results_and_meta(db_session, fake_embedder):
    spec = SourceSpec(type="manual", name="retrieval-test")
    result = ingest_documents(db_session, fake_embedder, source=spec, documents=[
        DocumentInput(title="HNSW doc", content="HNSW tuning parameters m ef_construction. " * 15),
        DocumentInput(title="Unrelated", content="completely unrelated topic about cooking. " * 15),
    ])

    settings = Settings()
    # Scope to this test's own source so committed ambient data (e.g. the Phase 3 eval corpus,
    # which also has an HNSW note) can't leak into the results — the shared dev DB is the test DB.
    hits, meta = hybrid_search(db_session, fake_embedder, settings, "HNSW tuning",
                               source_ids=[result.source_id])

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
    result = ingest_documents(db_session, fake_embedder, source=spec, documents=[
        DocumentInput(title="Rare term doc",
                      content="xyzquux is a very rare token that only appears here. " * 10),
    ])

    settings = Settings()
    hits, meta = hybrid_search(db_session, fake_embedder, settings, "xyzquux",
                               source_ids=[result.source_id])
    assert meta["candidates_fulltext"] >= 1
    assert meta["keyword_fallback_used"] is False
    assert any(h.method in ("fulltext", "hybrid") for h in hits)


def test_keyword_fallback_finds_uploaded_file_title_when_strict_fts_misses(
    db_session,
    fake_embedder,
):
    spec = SourceSpec(type="file_upload", name="upload-workflow-test")
    result = ingest_documents(db_session, fake_embedder, source=spec, documents=[
        DocumentInput(
            title="claude-code-notebooklm-obsidian-research-workflow",
            content=(
                "A research workflow moves captured source material into reviewed notes, "
                "then uses those notes as cited context for later questions. "
            ) * 20,
            content_type="application/pdf",
        ),
    ])

    settings = Settings(retrieval_min_vector_score=1.1)
    hits, meta = hybrid_search(
        db_session,
        fake_embedder,
        settings,
        "what is workflow pipline and how to setup",
        source_ids=[result.source_id],
    )

    assert hits
    assert meta["candidates_vector"] == 0
    assert meta["candidates_fulltext_strict"] == 0
    assert meta["keyword_fallback_used"] is True
    assert meta["candidates_keyword_fallback"] >= 1

    display = load_display_chunks(db_session, [h.chunk_id for h in hits])
    assert any(
        chunk.document_title == "claude-code-notebooklm-obsidian-research-workflow"
        for chunk in display.values()
    )

    empty_hits, empty_meta = hybrid_search(
        db_session,
        fake_embedder,
        settings,
        "anything about nothing?",
        source_ids=[result.source_id],
    )
    assert empty_hits == []
    assert empty_meta["candidates_keyword_fallback"] == 0
    assert empty_meta["keyword_fallback_used"] is False


def test_vector_threshold_filters_weak_vector_only_context(db_session, fake_embedder):
    spec = SourceSpec(type="manual", name="weak-vector-test")
    result = ingest_documents(db_session, fake_embedder, source=spec, documents=[
        DocumentInput(title="Cooking doc",
                      content="Sourdough hydration and oven spring notes. " * 20),
    ])

    settings = Settings(retrieval_min_vector_score=1.1)
    hits, meta = hybrid_search(db_session, fake_embedder, settings,
                               "When is my flight tomorrow?",
                               source_ids=[result.source_id])

    assert hits == []
    assert meta["candidates_vector_raw"] >= 1
    assert meta["candidates_vector"] == 0
    assert meta["vector_filtered_below_threshold"] >= 1
    assert meta["weak_context"] is True


def test_vector_threshold_preserves_fulltext_exact_hits(db_session, fake_embedder):
    spec = SourceSpec(type="manual", name="threshold-fts-test")
    result = ingest_documents(db_session, fake_embedder, source=spec, documents=[
        DocumentInput(title="Rare term doc",
                      content="plumbob-alpha appears in this note and nowhere else. " * 12),
    ])

    settings = Settings(retrieval_min_vector_score=1.1)
    hits, meta = hybrid_search(db_session, fake_embedder, settings, "plumbob-alpha",
                               source_ids=[result.source_id])

    assert hits
    assert meta["candidates_vector"] == 0
    assert meta["candidates_fulltext"] >= 1
    assert any(h.method == "fulltext" for h in hits)
