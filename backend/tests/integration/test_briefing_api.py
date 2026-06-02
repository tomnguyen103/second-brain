"""Integration tests for the briefing API (Phase 5): GET /briefing + /briefing/history.

GET /briefing returns the globally-latest briefing, so these tests clear the briefings table
*within the rolled-back transaction* (autouse fixture) to get a deterministic slate regardless
of any briefings committed into the shared dev DB by a live smoke. The delete never persists
(the fixture rolls back), so committed dev data is untouched — the right isolation pattern for
integration tests that share a DB (see implementation-notes, Phase 3).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.briefing.service import build_briefing
from app.db.models import Briefing
from app.llm.fake import FakeLLMClient

# Deterministic empty windows (no dev-DB coupling): each makes a "nothing new" briefing.
W1 = dict(since=datetime(2000, 1, 1, tzinfo=timezone.utc), now=datetime(2000, 1, 2, tzinfo=timezone.utc))
W2 = dict(since=datetime(2000, 1, 3, tzinfo=timezone.utc), now=datetime(2000, 1, 4, tzinfo=timezone.utc))


@pytest.fixture(autouse=True)
def _clean_briefings(db_session):
    db_session.execute(delete(Briefing))
    db_session.flush()


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
    assert data["total"] == 2
    ids = [item["id"] for item in data["briefings"]]
    assert ids == [b2.id, b1.id]      # newest first
