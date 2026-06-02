"""Integration tests for the worker dispatch loop + handler registry (Phase 5).

Tests drive `run_once(db, ...)` with the rolled-back db_session fixture and inject their own
handler dict — they never start the resident `run_loop` (known sharp edge #2). The fake jobs
use the allowed-but-out-of-scope `embed` type so they collide with no real handler.
"""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import Source
from app.jobs import handlers, queue, worker
from app.llm.fake import FakeLLMClient


def test_run_once_dispatches_and_marks_done(db_session, fake_embedder):
    calls = []

    def fake_handler(db, payload, *, embedder, llm):
        calls.append((payload, embedder, llm))
        return {"ok": True}

    enq = queue.enqueue(db_session, type="embed", payload={"x": 1})
    job = worker.run_once(
        db_session, embedder=fake_embedder, llm=FakeLLMClient(),
        max_attempts=3, handlers={"embed": fake_handler},
    )

    assert job is not None and job.id == enq.id
    assert job.status == "done"
    assert job.payload.get("result") == {"ok": True}
    assert len(calls) == 1
    assert calls[0][0] == {"x": 1}                  # payload passed through
    assert calls[0][1] is fake_embedder             # embedder injected
    assert isinstance(calls[0][2], FakeLLMClient)   # llm injected


def test_run_once_marks_failed_on_handler_exception(db_session, fake_embedder):
    def boom(db, payload, *, embedder, llm):
        raise RuntimeError("kaboom")

    queue.enqueue(db_session, type="embed")
    job = worker.run_once(
        db_session, embedder=fake_embedder, llm=FakeLLMClient(),
        max_attempts=1, handlers={"embed": boom},
    )

    assert job is not None
    assert job.status == "failed"
    assert job.attempts == 1
    assert "kaboom" in (job.last_error or "")


def test_run_once_rolls_back_partial_writes_on_failure(db_session, fake_embedder):
    # A handler that writes to the DB and then raises must leave no orphan row: the failure
    # record persists, but the handler's partial work is rolled back (one attempt = atomic).
    marker = "ORPHAN_MARKER_run_once_rollback"

    def writes_then_raises(db, payload, *, embedder, llm):
        db.add(Source(type="manual", name=marker))
        db.flush()
        raise RuntimeError("boom after a partial write")

    queue.enqueue(db_session, type="embed")
    job = worker.run_once(
        db_session, embedder=fake_embedder, llm=FakeLLMClient(),
        max_attempts=1, handlers={"embed": writes_then_raises},
    )

    assert job is not None and job.status == "failed"
    assert "boom" in (job.last_error or "")
    # the orphaned source was rolled back, not committed with the failure
    assert db_session.scalar(select(Source).where(Source.name == marker)) is None


def test_run_once_returns_none_when_no_job(db_session, fake_embedder):
    job = worker.run_once(
        db_session, embedder=fake_embedder, llm=FakeLLMClient(),
        max_attempts=3, handlers={},
    )
    assert job is None


def test_run_once_fails_unknown_type(db_session, fake_embedder):
    queue.enqueue(db_session, type="embed")
    job = worker.run_once(
        db_session, embedder=fake_embedder, llm=FakeLLMClient(),
        max_attempts=1, handlers={},   # nothing registered for 'embed'
    )
    assert job is not None
    assert job.status == "failed"
    assert "handler" in (job.last_error or "").lower()


def test_register_and_unregister_global_registry():
    def h(db, payload, *, embedder, llm):
        return None

    handlers.register("embed", h)
    try:
        assert handlers.HANDLERS.get("embed") is h
    finally:
        handlers.unregister("embed")   # always clean up, even if the assertion fails
    assert "embed" not in handlers.HANDLERS
