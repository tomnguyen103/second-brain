"""Queued research job endpoints.

These wrap the existing durable jobs table instead of running research inline. The worker
service processes rows with type='research' and stores the result in payload.result.
"""
from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import deps
from app.db.models import Job
from app.jobs import queue
from app.schemas.research import (
    JobStatus,
    ResearchJobCreateRequest,
    ResearchJobListResponse,
    ResearchJobOut,
)

router = APIRouter()


def _job_out(job: Job) -> ResearchJobOut:
    payload = job.payload or {}
    return ResearchJobOut(
        id=job.id,
        type="research",
        topic=payload.get("topic"),
        status=cast(JobStatus, job.status),
        attempts=job.attempts,
        last_error=job.last_error,
        scheduled_at=job.scheduled_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
        result=payload.get("result"),
    )


@router.post("/research/jobs", response_model=ResearchJobOut, status_code=status.HTTP_201_CREATED)
def enqueue_research_job(
    req: ResearchJobCreateRequest,
    db: Session = Depends(deps.get_db),
):
    topic = (req.topic or "").strip()
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="research topic is required",
        )
    source_urls = [url.strip() for url in req.source_urls if url.strip()]
    source_texts = [
        source.model_dump(exclude_none=True)
        for source in req.source_texts
        if source.text.strip()
    ]
    payload: dict = {"topic": topic}
    if source_urls:
        payload["source_urls"] = source_urls
    if source_texts:
        payload["source_texts"] = source_texts

    job = queue.enqueue(db, type="research", payload=payload)
    db.commit()
    db.refresh(job)
    return _job_out(job)


@router.get("/research/jobs", response_model=ResearchJobListResponse)
def list_research_jobs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(deps.get_db),
):
    jobs = db.scalars(
        select(Job)
        .where(Job.type == "research")
        .order_by(Job.created_at.desc(), Job.id.desc())
        .limit(limit)
    ).all()
    total = db.scalar(select(func.count()).select_from(Job).where(Job.type == "research")) or 0
    return ResearchJobListResponse(jobs=[_job_out(j) for j in jobs], total=total)


@router.get("/research/jobs/{job_id}", response_model=ResearchJobOut)
def get_research_job(
    job_id: int,
    db: Session = Depends(deps.get_db),
):
    job = db.get(Job, job_id)
    if job is None or job.type != "research":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research job not found")
    return _job_out(job)
