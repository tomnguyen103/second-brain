from __future__ import annotations

from sqlalchemy import select

from app.config import Settings
from app.db.models import Document, Source
from app.demo.seed_public import (
    PUBLIC_DEMO_DOCUMENTS,
    PUBLIC_DEMO_SOURCE_NAME,
    PUBLIC_DEMO_SUGGESTED_PROMPTS,
    seed_public_demo_corpus,
)
from app.retrieval.hybrid import hybrid_search


def test_seed_public_demo_corpus_ingests_searchable_public_safe_docs(
    db_session,
    fake_embedder,
):
    result = seed_public_demo_corpus(
        db_session,
        fake_embedder,
        Settings(llm_provider="fake"),
    )

    source = db_session.get(Source, result.source_id)
    docs = db_session.scalars(
        select(Document).where(Document.source_id == result.source_id).order_by(Document.title)
    ).all()
    tag_names = {tag.name for doc in docs for tag in doc.tags}

    assert source is not None
    assert source.type == "manual"
    assert source.name == PUBLIC_DEMO_SOURCE_NAME
    assert source.config["demo"] == "public"
    assert source.config["allows_public_uploads"] is False
    assert len(result.document_ids) == len(PUBLIC_DEMO_DOCUMENTS)
    assert result.embedded_count == len(PUBLIC_DEMO_DOCUMENTS)
    assert result.duplicate_count == 0
    assert result.suggested_prompts == PUBLIC_DEMO_SUGGESTED_PROMPTS
    assert any("Agentic RAG" in prompt for prompt in result.suggested_prompts)
    assert {doc.status for doc in docs} == {"embedded"}
    assert all(doc.raw_text for doc in docs)
    assert all(doc.metadata_["demo_visibility"] == "public-safe" for doc in docs)
    assert {"public-demo", "rag", "agentic-rag", "local-first", "mcp"} <= tag_names

    hits, meta = hybrid_search(
        db_session,
        fake_embedder,
        Settings(llm_provider="fake"),
        "Compare regular RAG and Agentic RAG in Second Brain",
        source_ids=[result.source_id],
    )

    assert hits
    assert meta["fused_returned"] > 0


def test_seed_public_demo_corpus_is_idempotent(db_session, fake_embedder):
    first = seed_public_demo_corpus(
        db_session,
        fake_embedder,
        Settings(llm_provider="fake"),
    )
    second = seed_public_demo_corpus(
        db_session,
        fake_embedder,
        Settings(llm_provider="fake"),
    )

    docs = db_session.scalars(
        select(Document).where(Document.source_id == first.source_id)
    ).all()

    assert second.source_id == first.source_id
    assert second.document_ids == first.document_ids
    assert second.embedded_count == 0
    assert second.duplicate_count == len(PUBLIC_DEMO_DOCUMENTS)
    assert len(docs) == len(PUBLIC_DEMO_DOCUMENTS)
