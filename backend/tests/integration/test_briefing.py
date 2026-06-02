"""Integration tests for the briefings table + build_briefing service (Phase 5)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.models import Briefing


def test_briefing_row_round_trips(db_session):
    now = datetime.now(timezone.utc)
    b = Briefing(
        generated_at=now,
        period_start=now - timedelta(hours=24),
        period_end=now,
        summary="canned summary",
        body_markdown="# Briefing\n\ncanned summary",
        document_count=2,
        model="fake",
    )
    db_session.add(b)
    db_session.flush()
    db_session.refresh(b)

    assert b.id is not None
    got = db_session.get(Briefing, b.id)
    assert got.summary == "canned summary"
    assert got.document_count == 2
    assert got.model == "fake"
    assert got.period_end == now


def test_briefing_model_is_nullable_for_nothing_new(db_session):
    # "nothing new" briefings make no LLM call, so model is NULL.
    now = datetime.now(timezone.utc)
    b = Briefing(
        generated_at=now,
        period_start=now,
        period_end=now,
        summary="Nothing new since the last briefing.",
        body_markdown="# Briefing",
        document_count=0,
        model=None,
    )
    db_session.add(b)
    db_session.flush()
    db_session.refresh(b)

    assert b.model is None
    assert b.document_count == 0
