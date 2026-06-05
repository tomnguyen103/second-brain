"""Integration tests for the briefings table + build_briefing service (Phase 5)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.briefing.service import NOTHING_NEW, build_briefing
from app.db.models import Briefing, Document
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.llm.fake import FakeLLMClient


def _ingest(db, embedder, titles, source_name="Briefing Test"):
    return ingest_documents(
        db, embedder,
        source=SourceSpec(type="manual", name=source_name),
        documents=[
            DocumentInput(title=t, content=f"{t} — body content for the briefing window.")
            for t in titles
        ],
    )


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


def test_build_briefing_summarizes_new_docs(db_session, fake_embedder):
    start = datetime.now(timezone.utc) - timedelta(seconds=1)
    _ingest(db_session, fake_embedder, ["Doc A", "Doc B"])

    b = build_briefing(db_session, FakeLLMClient(), since=start)

    assert b.id is not None
    assert b.document_count == 2
    assert b.model == "fake"          # fake driver still produces (and we store) a summary
    assert b.summary
    assert b.period_start == start
    assert "Doc A" in b.body_markdown and "Doc B" in b.body_markdown


def test_build_briefing_since_filter_excludes_old_docs(db_session, fake_embedder):
    start = datetime.now(timezone.utc) - timedelta(seconds=1)
    res = _ingest(db_session, fake_embedder, ["Fresh Doc", "Stale Doc"])
    stale_id = next(r.document_id for r in res.documents if r.title == "Stale Doc")
    stale = db_session.get(Document, stale_id)
    stale.created_at = start - timedelta(hours=2)   # back-date before the window
    db_session.flush()

    b = build_briefing(db_session, FakeLLMClient(), since=start)

    assert b.document_count == 1                     # only Fresh Doc is in (start, now]


def test_build_briefing_empty_period_is_nothing_new(db_session, fake_embedder):
    # A window far in the past is guaranteed empty regardless of dev-DB contents.
    since = datetime(2000, 1, 1, tzinfo=timezone.utc)
    now = datetime(2000, 1, 2, tzinfo=timezone.utc)

    b = build_briefing(db_session, FakeLLMClient(), since=since, now=now)

    assert b.document_count == 0
    assert b.model is None                           # no LLM call for an empty period
    assert NOTHING_NEW in b.summary
