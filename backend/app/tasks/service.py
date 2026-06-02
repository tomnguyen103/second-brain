"""Task service — backs the MCP create_task / list_tasks actions (ADR-0010).

Takes a `db` session (testable with the rolled-back fixture); the MCP layer owns the session.
Returns plain dataclasses so callers/transports don't touch detached ORM instances.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Task

_VALID_STATUS = {"open", "done", "cancelled"}


@dataclass
class TaskOut:
    id: int
    title: str
    detail: str | None
    status: str
    created_at: datetime


def _to_out(t: Task) -> TaskOut:
    return TaskOut(id=t.id, title=t.title, detail=t.detail, status=t.status, created_at=t.created_at)


def create_task(db: Session, title: str, detail: str | None = None) -> TaskOut:
    title = (title or "").strip()
    if not title:
        raise ValueError("task title is required")
    task = Task(title=title, detail=(detail or None), status="open")
    db.add(task)
    db.commit()
    db.refresh(task)
    return _to_out(task)


def list_tasks(db: Session, *, status: str | None = None, limit: int = 20) -> list[TaskOut]:
    if status is not None and status not in _VALID_STATUS:
        raise ValueError(f"invalid status filter: {status!r}")
    stmt = select(Task)
    if status:
        stmt = stmt.where(Task.status == status)
    stmt = stmt.order_by(Task.created_at.desc(), Task.id.desc()).limit(limit)
    return [_to_out(t) for t in db.scalars(stmt).all()]
