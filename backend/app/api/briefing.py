"""GET /briefing (latest) + GET /briefing/history — store-and-display delivery (ADR-0013 D3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import deps
from app.db.models import Briefing
from app.schemas.briefing import BriefingListResponse, BriefingOut

router = APIRouter(dependencies=[Depends(deps.require_api_access)])


@router.get("/briefing", response_model=BriefingOut)
def get_latest_briefing(db: Session = Depends(deps.get_db)):
    """Return the most recent stored briefing (404 until the first one is produced)."""
    briefing = db.scalar(
        select(Briefing).order_by(Briefing.generated_at.desc(), Briefing.id.desc()).limit(1)
    )
    if briefing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No briefing yet")
    return briefing


@router.get("/briefing/history", response_model=BriefingListResponse)
def get_briefing_history(
    db: Session = Depends(deps.get_db),
    limit: int = Query(20, ge=1, le=100),
):
    """Return recent briefings, newest first."""
    rows = db.scalars(
        select(Briefing).order_by(Briefing.generated_at.desc(), Briefing.id.desc()).limit(limit)
    ).all()
    total = db.scalar(select(func.count()).select_from(Briefing)) or 0
    return BriefingListResponse(briefings=list(rows), total=total)
