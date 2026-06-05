"""REST endpoints for user tasks created by the MCP task service."""
from __future__ import annotations

from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import deps
from app.schemas.tasks import (
    TaskCreateRequest,
    TaskListResponse,
    TaskOut,
    TaskStatus,
    TaskUpdateRequest,
)
from app.tasks import service

router = APIRouter(dependencies=[Depends(deps.require_api_access)])


def _task_out(t: service.TaskOut) -> TaskOut:
    return TaskOut(
        id=t.id,
        title=t.title,
        detail=t.detail,
        status=cast(TaskStatus, t.status),
        created_at=t.created_at,
    )


@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    status_filter: Literal["open", "done", "cancelled"] | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(deps.get_db),
):
    tasks = service.list_tasks(db, status=status_filter, limit=limit)
    return TaskListResponse(tasks=[_task_out(t) for t in tasks], total=len(tasks))


@router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    req: TaskCreateRequest,
    db: Session = Depends(deps.get_db),
):
    try:
        return _task_out(service.create_task(db, req.title, req.detail))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    req: TaskUpdateRequest,
    db: Session = Depends(deps.get_db),
):
    try:
        return _task_out(service.update_task_status(db, task_id, req.status))
    except service.TaskNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
