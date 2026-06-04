"""Pydantic schemas for task REST endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

TaskStatus = Literal["open", "done", "cancelled"]


class TaskCreateRequest(BaseModel):
    title: str
    detail: str | None = None


class TaskUpdateRequest(BaseModel):
    status: TaskStatus


class TaskOut(BaseModel):
    id: int
    title: str
    detail: str | None
    status: TaskStatus
    created_at: datetime


class TaskListResponse(BaseModel):
    tasks: list[TaskOut]
    total: int
