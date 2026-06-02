"""Pure research prompt building (ADR-0010). DB-free."""
from app.research.service import build_research_messages


def test_messages_shape():
    msgs = build_research_messages("  pgvector HNSW indexes  ")
    assert msgs[0].role == "system" and "research assistant" in msgs[0].content.lower()
    assert msgs[1].role == "user"
    assert "pgvector HNSW indexes" in msgs[1].content     # trimmed topic included
    assert msgs[1].content.strip().endswith("pgvector HNSW indexes")
