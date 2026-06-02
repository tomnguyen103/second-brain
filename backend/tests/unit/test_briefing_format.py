"""DB-free unit tests for the briefing pure functions (Phase 5)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.briefing.service import build_briefing_messages, format_briefing
from app.llm.base import LLMMessage

PS = datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)
PE = datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc)
DOCS = [
    ("HNSW tuning", "Notes", datetime(2026, 6, 2, 7, 0, tzinfo=timezone.utc)),
    ("RRF fusion", "Research", datetime(2026, 6, 2, 6, 0, tzinfo=timezone.utc)),
]


def test_build_briefing_messages_shape():
    msgs = build_briefing_messages(PS, PE, DOCS)
    assert len(msgs) == 2
    assert all(isinstance(m, LLMMessage) for m in msgs)
    assert msgs[0].role == "system"
    assert msgs[1].role == "user"
    # the user prompt names each new document and the count
    assert "HNSW tuning" in msgs[1].content
    assert "RRF fusion" in msgs[1].content
    assert "2" in msgs[1].content


def test_format_briefing_includes_summary_and_docs():
    md = format_briefing("Two new notes on retrieval.", PS, PE, DOCS, generated_at=PE)
    assert md.startswith("# Second Brain — morning briefing")
    assert "Two new notes on retrieval." in md
    assert "## New since last briefing" in md
    assert "- **HNSW tuning** — Notes" in md
    assert "- **RRF fusion** — Research" in md


def test_format_briefing_nothing_new():
    md = format_briefing("Nothing new since the last briefing.", PS, PE, [], generated_at=PE)
    assert "Nothing new since the last briefing." in md
    assert "_nothing new_" in md
