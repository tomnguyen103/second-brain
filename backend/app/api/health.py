from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import deps

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(deps.get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "down"

    embedder = deps.get_embedder.__wrapped__() if hasattr(deps.get_embedder, "__wrapped__") else None
    embedder_status = "loaded" if deps.get_embedder.cache_info().currsize > 0 else "unloaded"

    return {"status": "ok", "db": db_status, "embedder": embedder_status}
