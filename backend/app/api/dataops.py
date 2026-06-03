"""Admin / data-subject endpoints (Phase 6, ADR-0012).

GDPR "right to access" (export) and "right to erasure" (delete-my-data) at source
granularity, plus a retention-purge trigger. All are guarded by `require_admin` (Bearer
token) since they read/destroy user data. Each commits so its audit row persists.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import deps
from app.dataops import erasure, retention
from app.db.models import Source

router = APIRouter()


@router.get("/data/export")
def export_data(
    source_id: int,
    db: Session = Depends(deps.get_db),
    settings=Depends(deps.get_settings),
    _: bool = Depends(deps.require_admin),
):
    """Export a source and its documents as JSON (GDPR right-to-access). Audited."""
    try:
        result = erasure.export_source(db, source_id, audit_enabled=settings.audit_enabled)
    except erasure.SourceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    db.commit()
    return result


@router.delete("/data/sources/{source_id}")
def delete_data(
    source_id: int,
    confirm_source_name: str | None = None,
    confirm_token: str | None = None,
    db: Session = Depends(deps.get_db),
    settings=Depends(deps.get_settings),
    _: bool = Depends(deps.require_admin),
):
    """Delete a source and its whole subtree (GDPR right-to-erasure). Audited."""
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    preview = erasure.preview_delete_source(db, source_id)
    if confirm_source_name != source.name and confirm_token != preview["confirmation_token"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=preview)
    try:
        deleted = erasure.delete_source(db, source_id, audit_enabled=settings.audit_enabled)
    except erasure.SourceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    db.commit()
    return {"source_id": source_id, "documents_deleted": deleted}


@router.post("/admin/retention/purge")
def purge_retention(
    older_than_days: int | None = None,
    dry_run: bool = True,
    confirm: str | None = None,
    db: Session = Depends(deps.get_db),
    settings=Depends(deps.get_settings),
    _: bool = Depends(deps.require_admin),
):
    """Preview or null raw_text for documents past the retention TTL."""
    days = older_than_days if older_than_days is not None else settings.retention_raw_text_days
    if days < settings.min_retention_purge_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"older_than_days must be at least {settings.min_retention_purge_days}",
        )
    if dry_run:
        would_purge = retention.count_purge_candidates(db, older_than_days=days)
        return {"dry_run": True, "older_than_days": days, "would_purge": would_purge}
    if confirm != "purge raw_text":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='resubmit with dry_run=false and confirm="purge raw_text"',
        )
    purged = retention.purge_raw_text(
        db, older_than_days=days, audit_enabled=settings.audit_enabled
    )
    db.commit()
    return {"dry_run": False, "older_than_days": days, "purged": purged}
