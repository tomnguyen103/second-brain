"""Pure digest formatting (ADR-0010). DB-free."""
from datetime import datetime, timezone

from app.digest.service import DigestData, format_digest


def test_format_with_docs():
    data = DigestData(
        generated_at=datetime(2026, 6, 2, 14, 30, tzinfo=timezone.utc),
        n_sources=3, n_documents=12, n_chunks=88,
        recent_documents=[("HNSW index tuning", "Eval Corpus",
                           datetime(2026, 6, 1, tzinfo=timezone.utc))],
    )
    out = format_digest(data)
    assert "# Second Brain — daily digest" in out
    assert "2026-06-02 14:30 UTC" in out
    assert "**12** documents across **3** sources" in out
    assert "**88** chunks indexed" in out
    assert "**HNSW index tuning** — Eval Corpus · 2026-06-01" in out


def test_format_empty():
    data = DigestData(generated_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
                      n_sources=0, n_documents=0, n_chunks=0)
    out = format_digest(data)
    assert "_nothing yet_" in out
