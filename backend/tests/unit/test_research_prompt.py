"""Pure research prompt/source handling (ADR-0010). DB-free."""
import pytest

from app.research.service import build_research_messages, collect_research_sources


def test_messages_shape():
    msgs = build_research_messages("  pgvector HNSW indexes  ")
    assert msgs[0].role == "system" and "research assistant" in msgs[0].content.lower()
    assert msgs[1].role == "user"
    assert "pgvector HNSW indexes" in msgs[1].content     # trimmed topic included
    assert msgs[1].content.strip().endswith("pgvector HNSW indexes")


def test_messages_include_provided_source_context():
    sources = collect_research_sources(
        source_texts=[{
            "title": "RRF note",
            "uri": "manual://rrf",
            "text": "Reciprocal rank fusion combines independently ranked retrieval results.",
        }]
    )

    msgs = build_research_messages("reciprocal rank fusion", sources)

    assert "[S1] RRF note" in msgs[1].content
    assert "manual://rrf" in msgs[1].content
    assert "using only the source excerpts" in msgs[1].content
    assert "Reciprocal rank fusion combines" in msgs[1].content


def test_collect_research_sources_rejects_non_public_urls():
    with pytest.raises(ValueError, match="public|http"):
        collect_research_sources(source_urls=["http://127.0.0.1/internal"])
