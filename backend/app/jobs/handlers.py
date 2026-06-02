"""Job handler registry (Phase 5, ADR-0013).

Maps a job ``type`` to a handler ``handler(db, payload, *, embedder, llm) -> dict | None``.
Production handlers (``briefing``, ``research``) register themselves when this module is
imported (added in Tasks 5/6), so importing ``app.jobs.handlers`` populates the registry for
the worker. Tests inject their own dict into ``run_once(..., handlers=...)`` instead of
mutating the global, and use ``register``/``unregister`` for the registry itself.
"""
from __future__ import annotations

from collections.abc import Callable

# type -> handler(db, payload, *, embedder, llm) -> dict | None
HANDLERS: dict[str, Callable] = {}


def register(job_type: str, handler: Callable) -> Callable:
    """Register (or replace) the handler for a job type. Returns the handler."""
    HANDLERS[job_type] = handler
    return handler


def unregister(job_type: str) -> None:
    """Remove a handler if present (used by tests to clean up)."""
    HANDLERS.pop(job_type, None)
