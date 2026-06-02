"""Durable job-queue primitives over the `jobs` table (ADR-0004).

The queue is the source of truth for background work: enqueue a row, a worker claims the
next eligible one with `SELECT ... FOR UPDATE SKIP LOCKED` (restart-safe, concurrency-safe
for N workers), then marks it done or failed. Retries are tracked on the row itself
(`attempts`/`last_error`); `status='failed'` is the dead-letter view.

These primitives only `flush()` — the worker (`app.jobs.worker.run_once`) owns the commit so
each job attempt is one transaction; the enqueue CLI commits explicitly.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(timezone.utc)


def enqueue(
    db: Session,
    *,
    type: str,
    payload: dict | None = None,
    scheduled_at: datetime | None = None,
) -> Job:
    """Insert a queued job. `scheduled_at` in the future delays it until then."""
    job = Job(type=type, payload=payload or {}, scheduled_at=_now(scheduled_at))
    db.add(job)
    db.flush()
    db.refresh(job)
    return job


def claim_next(
    db: Session,
    *,
    types: Sequence[str] | None = None,
    now: datetime | None = None,
) -> Job | None:
    """Claim the next eligible job, flipping it queued -> running.

    Eligible = `status='queued'` and `scheduled_at <= now`, oldest first. `FOR UPDATE SKIP
    LOCKED` lets multiple workers claim disjoint rows without blocking each other. Returns
    None when nothing is eligible.
    """
    now = _now(now)
    stmt = select(Job).where(Job.status == "queued", Job.scheduled_at <= now)
    if types:
        stmt = stmt.where(Job.type.in_(list(types)))
    stmt = stmt.order_by(Job.scheduled_at, Job.id).with_for_update(skip_locked=True).limit(1)

    job = db.scalar(stmt)
    if job is None:
        return None
    job.status = "running"
    job.started_at = now
    db.flush()
    return job


def mark_done(db: Session, job: Job, result: dict | None = None) -> Job:
    """Mark a job done. A handler result is stashed under `payload.result` (the jobs table
    has no dedicated result column) so it stays inspectable."""
    job.status = "done"
    job.finished_at = _now()
    if result is not None:
        job.payload = {**(job.payload or {}), "result": result}
    db.flush()
    return job


def mark_failed(db: Session, job: Job, error: str, *, max_attempts: int) -> Job:
    """Record a failed attempt. Requeue for retry while `attempts < max_attempts`,
    otherwise dead-letter it (`status='failed'`)."""
    job.attempts += 1
    job.last_error = str(error)
    if job.attempts < max_attempts:
        job.status = "queued"      # eligible to be re-claimed
        job.started_at = None
    else:
        job.status = "failed"
        job.finished_at = _now()
    db.flush()
    return job
