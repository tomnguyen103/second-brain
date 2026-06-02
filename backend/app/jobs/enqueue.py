"""Enqueue a job from the command line (Phase 5, ADR-0013).

The OS-cron scheduler (D2 — no resident scheduler) uses this to enqueue the daily briefing:

    python -m app.jobs.enqueue briefing
    python -m app.jobs.enqueue research --topic "reciprocal rank fusion"

Thin wiring over the tested ``queue.enqueue``; the worker (``app.jobs.worker --loop``) then
drains the row.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from app.jobs import queue


def main(argv: Sequence[str] | None = None) -> None:  # pragma: no cover - CLI wiring
    parser = argparse.ArgumentParser(prog="python -m app.jobs.enqueue")
    parser.add_argument("type", choices=["briefing", "research"], help="job type to enqueue")
    parser.add_argument("--topic", help="topic for a research job")
    parser.add_argument("--payload", help="raw JSON payload (overrides --topic)")
    args = parser.parse_args(argv)

    payload: dict = {}
    if args.payload:
        payload = json.loads(args.payload)
    elif args.topic:
        payload = {"topic": args.topic}

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        job = queue.enqueue(db, type=args.type, payload=payload)
        db.commit()
        print(f"enqueued job {job.id} ({job.type})")


if __name__ == "__main__":  # pragma: no cover
    main()
