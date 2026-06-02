"""Integration tests for the briefing API (Phase 5): GET /briefing + /briefing/history."""
from __future__ import annotations

from datetime import datetime, timezone

from app.briefing.service import build_briefing
from app.llm.fake import FakeLLMClient

# Deterministic empty windows (no dev-DB coupling): each makes a "nothing new" briefing.
W1 = dict(since=datetime(2000, 1, 1, tzinfo=timezone.utc), now=datetime(2000, 1, 2, tzinfo=timezone.utc))
W2 = dict(since=datetime(2000, 1, 3, tzinfo=timezone.utc), now=datetime(2000, 1, 4, tzinfo=timezone.utc))


def test_get_briefing_404_when_none(client):
    resp = client.get("/briefing")
    assert resp.status_code == 404


def test_get_briefing_returns_latest(client, db_session):
    b = build_briefing(db_session, FakeLLMClient(), **W1)

    resp = client.get("/briefing")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == b.id
    assert data["summary"] == b.summary
    assert data["document_count"] == 0
    assert data["model"] is None
    assert data["body_markdown"].startswith("# Second Brain")


def test_get_briefing_history_newest_first(client, db_session):
    b1 = build_briefing(db_session, FakeLLMClient(), **W1)
    b2 = build_briefing(db_session, FakeLLMClient(), **W2)

    resp = client.get("/briefing/history?limit=10")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    ids = [item["id"] for item in data["briefings"]]
    assert ids[0] == b2.id        # newest first
    assert b1.id in ids
