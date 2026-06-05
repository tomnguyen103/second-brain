"""Admin / data-subject endpoints (Phase 6, ADR-0012).

GDPR "right to access" (export) and "right to erasure" (delete-my-data) at source
granularity, plus a retention-purge trigger. These routes require normal single-owner
API access and an additional admin header because they read or destroy user data.
Each commits so its audit row persists.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import deps
from app.dataops import erasure, retention

router = APIRouter(dependencies=[Depends(deps.require_api_access)])


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
    db: Session = Depends(deps.get_db),
    settings=Depends(deps.get_settings),
    _: bool = Depends(deps.require_admin),
):
    """Delete a source and its whole subtree (GDPR right-to-erasure). Audited."""
    try:
        deleted = erasure.delete_source(db, source_id, audit_enabled=settings.audit_enabled)
    except erasure.SourceNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    db.commit()
    return {"source_id": source_id, "documents_deleted": deleted}


@router.post("/admin/retention/purge")
def purge_retention(
    older_than_days: int | None = None,
    db: Session = Depends(deps.get_db),
    settings=Depends(deps.get_settings),
    _: bool = Depends(deps.require_admin),
):
    """Null raw_text for documents past the retention TTL. Defaults to the configured TTL."""
    days = older_than_days if older_than_days is not None else settings.retention_raw_text_days
    purged = retention.purge_raw_text(
        db, older_than_days=days, audit_enabled=settings.audit_enabled
    )
    db.commit()
    return {"older_than_days": days, "purged": purged}
