"""Source and document overview endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, selectinload

from app import deps
from app.db.models import Chunk, Document, Source
from app.schemas.sources import (
    DocumentListResponse,
    DocumentSummary,
    SourceListResponse,
    SourceOut,
    SourceSummary,
)

router = APIRouter(dependencies=[Depends(deps.require_api_access)])


@router.get("/sources", response_model=SourceListResponse)
def list_sources(
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(deps.get_db),
):
    stats = (
        select(
            Document.source_id.label("source_id"),
            func.count(distinct(Document.id)).label("document_count"),
            func.count(Chunk.id).label("chunk_count"),
            func.max(func.coalesce(Document.ingested_at, Document.created_at)).label(
                "latest_document_at"
            ),
        )
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        .group_by(Document.source_id)
        .subquery()
    )
    rows = db.execute(
        select(
            Source,
            func.coalesce(stats.c.document_count, 0),
            func.coalesce(stats.c.chunk_count, 0),
            stats.c.latest_document_at,
        )
        .outerjoin(stats, stats.c.source_id == Source.id)
        .order_by(Source.updated_at.desc(), Source.id.desc())
        .limit(limit)
    ).all()
    total = db.scalar(select(func.count()).select_from(Source)) or 0
    sources = [
        SourceSummary(
            id=source.id,
            type=source.type,
            name=source.name,
            uri=source.uri,
            created_at=source.created_at,
            updated_at=source.updated_at,
            document_count=document_count,
            chunk_count=chunk_count,
            latest_document_at=latest_document_at,
        )
        for source, document_count, chunk_count, latest_document_at in rows
    ]
    return SourceListResponse(sources=sources, total=total)


@router.get("/sources/{source_id}/documents", response_model=DocumentListResponse)
def list_source_documents(
    source_id: int,
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(deps.get_db),
):
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    docs = db.scalars(
        select(Document)
        .where(Document.source_id == source_id)
        .options(selectinload(Document.tags), selectinload(Document.chunks))
        .order_by(Document.created_at.desc(), Document.id.desc())
        .limit(limit)
    ).all()
    total = db.scalar(
        select(func.count()).select_from(Document).where(Document.source_id == source_id)
    ) or 0
    return DocumentListResponse(
        source=SourceOut.model_validate(source),
        documents=[
            DocumentSummary(
                id=doc.id,
                source_id=doc.source_id,
                title=doc.title,
                external_id=doc.external_id,
                content_type=doc.content_type,
                content_hash=doc.content_hash,
                status=doc.status,
                tags=[tag.name for tag in doc.tags],
                chunk_count=len(doc.chunks),
                raw_text_available=doc.raw_text is not None,
                ingested_at=doc.ingested_at,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
            )
            for doc in docs
        ],
        total=total,
    )
