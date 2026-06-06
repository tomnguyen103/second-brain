"""Local operator status for the web workspace."""
from __future__ import annotations

from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import deps
from app.config import Settings
from app.db.models import Chunk, Document, Embedding, Job, Source
from app.schemas.status import (
    AppStatusResponse,
    DatabaseStatus,
    KnowledgeStatus,
    RuntimeStatus,
    WorkerStatus,
)

router = APIRouter(dependencies=[Depends(deps.require_api_access)])


def _migration_head() -> str | None:
    backend_dir = Path(__file__).resolve().parents[2]
    alembic_cfg = AlembicConfig(str(backend_dir / "alembic.ini"))
    return ScriptDirectory.from_config(alembic_cfg).get_current_head()


def _database_status(db: Session) -> DatabaseStatus:
    current: str | None = None
    head: str | None = None
    try:
        db.execute(text("SELECT 1"))
        current = db.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
        head = _migration_head()
        return DatabaseStatus(
            reachable=True,
            migration_current=current,
            migration_head=head,
            migrated=bool(current and head and current == head),
        )
    except Exception as exc:
        return DatabaseStatus(
            reachable=False,
            migration_current=current,
            migration_head=head,
            migrated=False,
            error=str(exc),
        )


def _worker_status(db: Session) -> WorkerStatus:
    counts = {status: 0 for status in ("queued", "running", "done", "failed")}
    for status, count in db.execute(select(Job.status, func.count(Job.id)).group_by(Job.status)):
        counts[str(status)] = int(count)

    if counts["failed"]:
        status = "attention"
    elif counts["running"]:
        status = "active"
    elif counts["queued"]:
        status = "pending"
    else:
        status = "idle"

    latest_finished_at = db.scalar(select(func.max(Job.finished_at)).select_from(Job))
    latest_error = db.scalar(
        select(Job.last_error)
        .where(Job.status == "failed", Job.last_error.is_not(None))
        .order_by(Job.id.desc())
        .limit(1)
    )
    return WorkerStatus(
        status=status,
        queued=counts["queued"],
        running=counts["running"],
        done=counts["done"],
        failed=counts["failed"],
        latest_finished_at=latest_finished_at,
        latest_error=latest_error,
    )


def _knowledge_status(db: Session) -> KnowledgeStatus:
    return KnowledgeStatus(
        source_count=db.scalar(select(func.count(Source.id))) or 0,
        document_count=db.scalar(select(func.count(Document.id))) or 0,
        embedded_document_count=(
            db.scalar(select(func.count(Document.id)).where(Document.status == "embedded")) or 0
        ),
        chunk_count=db.scalar(select(func.count(Chunk.id))) or 0,
        embedding_count=db.scalar(select(func.count(Embedding.id))) or 0,
        latest_document_at=db.scalar(
            select(func.max(func.coalesce(Document.ingested_at, Document.created_at)))
        ),
    )


def _runtime_status(settings: Settings) -> RuntimeStatus:
    llm_model = settings.gemini_model if settings.llm_provider == "gemini" else settings.ollama_model
    if settings.llm_provider == "fake":
        llm_model = "fake"
    embedding_model = (
        settings.gemini_embedding_model
        if settings.embedding_provider == "gemini"
        else settings.embedding_model
    )
    return RuntimeStatus(
        llm_provider=settings.llm_provider,
        llm_model=llm_model,
        embedding_provider=settings.embedding_provider,
        embedding_model=embedding_model,
        agentic_rag_enabled=settings.agentic_rag_enabled,
        mcp_mutations_enabled=settings.mcp_enable_mutations,
    )


@router.get("/status", response_model=AppStatusResponse)
def get_status(
    db: Session = Depends(deps.get_db),
    settings: Settings = Depends(deps.get_settings),
):
    database = _database_status(db)
    worker = _worker_status(db) if database.reachable else WorkerStatus(
        status="unknown",
        queued=0,
        running=0,
        done=0,
        failed=0,
        latest_finished_at=None,
        latest_error=None,
    )
    knowledge = _knowledge_status(db) if database.reachable else KnowledgeStatus(
        source_count=0,
        document_count=0,
        embedded_document_count=0,
        chunk_count=0,
        embedding_count=0,
        latest_document_at=None,
    )
    status = "ok" if database.reachable and database.migrated and worker.status != "attention" else "attention"
    return AppStatusResponse(
        status=status,
        database=database,
        worker=worker,
        knowledge=knowledge,
        runtime=_runtime_status(settings),
    )
