"""Poll-based job worker (Phase 5, ADR-0013).

``run_once`` is the unit of work — claim one job, dispatch it to its handler, then mark it
done or failed and commit. It is what the integration tests drive (with the rolled-back
db_session fixture). ``run_loop`` is the resident ``--loop`` process for the deploy stack;
it is intentionally NOT exercised by tests (it never terminates — sharp edge #2). ``main``
wires ``--once`` / ``--loop`` and builds the embedder/LLM once (like the MCP tools).

Scheduling is OS cron (ADR-0013 D2): cron enqueues the daily ``briefing`` job; this worker
just drains the queue.
"""
from __future__ import annotations

import argparse
import time
from collections.abc import Callable, Sequence

from sqlalchemy.orm import Session

from app.cache.redis_client import get_redis_client
from app.cache.search import bump_search_cache_epoch
from app.config import settings
from app.jobs import queue
from app.jobs.handlers import HANDLERS


def run_once(
    db: Session,
    *,
    embedder,
    llm,
    max_attempts: int,
    handlers: dict[str, Callable] | None = None,
    types: Sequence[str] | None = None,
    redis_client=None,
    cache_settings=None,
):
    """Claim and process a single job. Returns the Job (done/failed) or None if the queue
    is empty. Any handler exception is recorded on the job (`mark_failed`) rather than raised.

    One attempt is atomic: the claim (queued -> running) is flushed before the handler runs,
    and the final done/failed state commits once at the end. On failure, handler writes are
    rolled back before the failure is recorded, so a failed job never leaves orphaned rows.
    """
    registry = HANDLERS if handlers is None else handlers
    cfg = cache_settings or settings
    job = queue.claim_next(db, types=types)
    if job is None:
        return None

    handler = registry.get(job.type)
    invalidate_search = False
    # SAVEPOINT around the handler: on failure its partial writes roll back while the claim
    # (queued -> running, taken before the savepoint) survives, so a failed job never commits
    # orphaned rows (e.g. a half-written Briefing or research note) alongside the failure record.
    savepoint = db.begin_nested()
    try:
        if handler is None:
            raise LookupError(f"no handler registered for job type {job.type!r}")
        result = handler(db, job.payload, embedder=embedder, llm=llm)
        queue.mark_done(db, job, result=result)
        if savepoint.is_active:
            savepoint.commit()
        invalidate_search = isinstance(result, dict) and bool(result.get("searchable"))
    except Exception as exc:  # noqa: BLE001 — any handler failure is recorded on the job row
        if savepoint.is_active:
            savepoint.rollback()
        queue.mark_failed(db, job, str(exc), max_attempts=max_attempts)
    db.commit()
    if invalidate_search:
        bump_search_cache_epoch(redis_client, cfg)
    return job


def run_loop(
    session_factory,
    *,
    embedder,
    llm,
    max_attempts: int,
    poll_seconds: float,
    types: Sequence[str] | None = None,
    redis_client=None,
    cache_settings=None,
) -> None:  # pragma: no cover - resident deploy process, not unit-tested (sharp edge #2)
    """Poll the queue forever: drain eligible jobs, then sleep ``poll_seconds`` when idle.

    A fresh session per job keeps each attempt's transaction isolated. Deploy-stack only.
    """
    while True:
        with session_factory() as db:
            job = run_once(
                db,
                embedder=embedder,
                llm=llm,
                max_attempts=max_attempts,
                types=types,
                redis_client=redis_client,
                cache_settings=cache_settings,
            )
        if job is None:
            time.sleep(poll_seconds)


def main(argv: Sequence[str] | None = None) -> None:  # pragma: no cover - CLI wiring
    parser = argparse.ArgumentParser(prog="python -m app.jobs.worker")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--once", action="store_true", help="process a single job and exit")
    group.add_argument("--loop", action="store_true", help="poll continuously (deploy service)")
    args = parser.parse_args(argv)

    from app.db.session import SessionLocal
    from app.deps import get_embedder
    from app.llm.factory import get_llm_client

    embedder = get_embedder()
    llm = get_llm_client(settings)
    redis_client = get_redis_client(settings)

    if args.loop:
        run_loop(
            SessionLocal, embedder=embedder, llm=llm,
            max_attempts=settings.job_max_attempts,
            poll_seconds=settings.worker_poll_seconds,
            redis_client=redis_client,
            cache_settings=settings,
        )
    else:
        with SessionLocal() as db:
            job = run_once(
                db,
                embedder=embedder,
                llm=llm,
                max_attempts=settings.job_max_attempts,
                redis_client=redis_client,
                cache_settings=settings,
            )
        if job is None:
            print("no eligible job")
        else:
            print(f"job {job.id} ({job.type}) -> {job.status}")


if __name__ == "__main__":  # pragma: no cover
    main()
