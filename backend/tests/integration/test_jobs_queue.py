"""Integration tests for the durable job queue primitives (Phase 5, ADR-0004)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.jobs import queue


def test_enqueue_creates_queued_job(db_session):
    job = queue.enqueue(db_session, type="briefing", payload={"k": "v"})
    assert job.id is not None
    assert job.type == "briefing"
    assert job.status == "queued"
    assert job.attempts == 0
    assert job.payload == {"k": "v"}
    assert job.scheduled_at is not None


def test_claim_next_flips_to_running_and_is_exclusive(db_session):
    enqueued = queue.enqueue(db_session, type="briefing")
    claimed = queue.claim_next(db_session)
    assert claimed is not None
    assert claimed.id == enqueued.id
    assert claimed.status == "running"
    assert claimed.started_at is not None
    # A second claim sees no 'queued' row. The status flip (queued->running) is the
    # N-worker guard; FOR UPDATE SKIP LOCKED covers real concurrency, which a single
    # test transaction cannot simulate (known sharp edge #1).
    assert queue.claim_next(db_session) is None


def test_claim_next_respects_types_filter(db_session):
    queue.enqueue(db_session, type="briefing")
    assert queue.claim_next(db_session, types=["research"]) is None
    claimed = queue.claim_next(db_session, types=["briefing"])
    assert claimed is not None and claimed.type == "briefing"


def test_claim_next_skips_future_scheduled(db_session):
    now = datetime.now(timezone.utc)
    queue.enqueue(db_session, type="briefing", scheduled_at=now + timedelta(hours=1))
    assert queue.claim_next(db_session, now=now) is None


def test_mark_done_sets_status_finished_and_result(db_session):
    job = queue.enqueue(db_session, type="briefing")
    queue.claim_next(db_session)
    queue.mark_done(db_session, job, result={"briefing_id": 1})
    assert job.status == "done"
    assert job.finished_at is not None
    assert job.payload.get("result") == {"briefing_id": 1}


def test_mark_failed_retries_until_max_attempts(db_session):
    job = queue.enqueue(db_session, type="briefing")
    queue.claim_next(db_session)

    queue.mark_failed(db_session, job, "boom", max_attempts=3)
    assert job.status == "queued"          # attempts 1 < 3 -> requeued for retry
    assert job.attempts == 1
    assert job.last_error == "boom"

    queue.mark_failed(db_session, job, "boom2", max_attempts=3)
    assert job.status == "queued"          # attempts 2 < 3 -> still requeued
    assert job.attempts == 2

    queue.mark_failed(db_session, job, "boom3", max_attempts=3)
    assert job.status == "failed"          # attempts 3 == max -> dead-lettered
    assert job.attempts == 3
    assert job.finished_at is not None
    assert job.last_error == "boom3"
