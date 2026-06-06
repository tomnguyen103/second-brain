"""Source and document overview endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, distinct, func, select
from sqlalchemy.orm import Session, selectinload

from app import deps
from app.cache.embedding import encode_with_cache
from app.cache.search import bump_search_cache_epoch
from app.dataops import audit
from app.db.models import Chunk, Document, Embedding, Source
from app.ingest.chunking import chunk_text
from app.ingest.hashing import content_hash
from app.schemas.sources import (
    DeleteDocumentResponse,
    DocumentContentResponse,
    DocumentContentUpdateRequest,
    DocumentListResponse,
    DocumentSummary,
    DocumentUpdateRequest,
    SourceListResponse,
    SourceOut,
    SourceSummary,
    SourceUpdateRequest,
)

router = APIRouter(dependencies=[Depends(deps.require_api_access)])


def _document_summary(doc: Document) -> DocumentSummary:
    return DocumentSummary(
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


def _load_document(db: Session, document_id: int) -> Document | None:
    return db.scalars(
        select(Document)
        .where(Document.id == document_id)
        .options(
            selectinload(Document.source),
            selectinload(Document.tags),
            selectinload(Document.chunks),
        )
    ).first()


def _document_content_response(
    doc: Document,
    *,
    max_chars: int,
) -> DocumentContentResponse:
    if doc.raw_text is not None:
        content = doc.raw_text
        content_source = "raw_text"
    elif doc.chunks:
        content = "\n\n".join(
            chunk.content for chunk in sorted(doc.chunks, key=lambda c: c.chunk_index)
        )
        content_source = "chunks"
    else:
        content = None
        content_source = "unavailable"

    truncated = content is not None and len(content) > max_chars
    if truncated:
        content = content[:max_chars].rstrip()

    return DocumentContentResponse(
        source=SourceOut.model_validate(doc.source),
        document=_document_summary(doc),
        content=content,
        content_source=content_source,
        truncated=truncated,
    )


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


@router.patch("/sources/{source_id}", response_model=SourceOut)
def update_source(
    source_id: int,
    req: SourceUpdateRequest,
    db: Session = Depends(deps.get_db),
    settings=Depends(deps.get_settings),
    _: bool = Depends(deps.require_admin),
):
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    previous_name = source.name
    source.name = req.name
    audit.record(
        db,
        actor="operator",
        action="update",
        entity_type="source",
        entity_id=source_id,
        detail={"field": "name", "previous": previous_name, "next": req.name},
        enabled=settings.audit_enabled,
    )
    db.commit()
    db.refresh(source)
    return SourceOut.model_validate(source)


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
        documents=[_document_summary(doc) for doc in docs],
        total=total,
    )


@router.get("/documents/{document_id}/content", response_model=DocumentContentResponse)
def get_document_content(
    document_id: int,
    max_chars: int = Query(2000000, ge=500, le=2000000),
    db: Session = Depends(deps.get_db),
):
    doc = _load_document(db, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return _document_content_response(doc, max_chars=max_chars)


@router.get("/documents/{document_id}/preview", response_model=DocumentContentResponse)
def preview_document(
    document_id: int,
    max_chars: int = Query(12000, ge=500, le=20000),
    db: Session = Depends(deps.get_db),
):
    return get_document_content(document_id=document_id, max_chars=max_chars, db=db)


@router.patch("/documents/{document_id}", response_model=DocumentSummary)
def update_document(
    document_id: int,
    req: DocumentUpdateRequest,
    db: Session = Depends(deps.get_db),
    settings=Depends(deps.get_settings),
    _: bool = Depends(deps.require_admin),
):
    doc = db.scalars(
        select(Document)
        .where(Document.id == document_id)
        .options(selectinload(Document.tags), selectinload(Document.chunks))
    ).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    previous_title = doc.title
    doc.title = req.title
    audit.record(
        db,
        actor="operator",
        action="update",
        entity_type="document",
        entity_id=document_id,
        detail={"field": "title", "previous": previous_title, "next": req.title},
        enabled=settings.audit_enabled,
    )
    db.commit()
    db.refresh(doc)
    return _document_summary(doc)


@router.patch("/documents/{document_id}/content", response_model=DocumentContentResponse)
def update_document_content(
    document_id: int,
    req: DocumentContentUpdateRequest,
    max_chars: int = Query(2000000, ge=500, le=2000000),
    db: Session = Depends(deps.get_db),
    settings=Depends(deps.get_settings),
    redis_client=Depends(deps.get_redis),
    embedder=Depends(deps.get_embedder),
    _: bool = Depends(deps.require_admin),
):
    doc = _load_document(db, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    next_hash = content_hash(req.content)
    duplicate_id = db.scalar(
        select(Document.id).where(
            Document.source_id == doc.source_id,
            Document.content_hash == next_hash,
            Document.id != document_id,
        )
    )
    if duplicate_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"content duplicates document {duplicate_id} in this source",
        )

    pieces = chunk_text(
        req.content,
        embedder.count_tokens,
        settings.chunk_target_tokens,
        settings.chunk_overlap_ratio,
    )
    vectors = (
        encode_with_cache(
            embedder,
            [piece.content for piece in pieces],
            redis_client=redis_client,
            settings=settings,
            namespace="content",
        )
        if pieces
        else []
    )

    previous_hash = doc.content_hash
    previous_chunk_count = db.scalar(
        select(func.count(Chunk.id)).where(Chunk.document_id == document_id)
    ) or 0

    db.execute(
        delete(Chunk).where(Chunk.document_id == document_id),
        execution_options={"synchronize_session": False},
    )
    doc.raw_text = req.content
    doc.content_hash = next_hash
    doc.status = "embedded"
    doc.ingested_at = datetime.now(timezone.utc)

    for piece, vector in zip(pieces, vectors):
        chunk = Chunk(
            document_id=doc.id,
            chunk_index=piece.index,
            content=piece.content,
            token_count=piece.token_count,
            char_start=piece.char_start,
            char_end=piece.char_end,
        )
        db.add(chunk)
        db.flush()
        db.add(
            Embedding(
                chunk_id=chunk.id,
                model=embedder.model_name,
                dim=embedder.dim,
                embedding=vector,
            )
        )

    audit.record(
        db,
        actor="operator",
        action="update",
        entity_type="document",
        entity_id=document_id,
        detail={
            "field": "content",
            "previous_hash": previous_hash,
            "next_hash": next_hash,
            "previous_chunk_count": previous_chunk_count,
            "next_chunk_count": len(pieces),
        },
        enabled=settings.audit_enabled,
    )
    db.commit()
    bump_search_cache_epoch(redis_client, settings)
    db.expire_all()
    updated = _load_document(db, document_id)
    if updated is None:  # Defensive; the row existed and was not deleted.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return _document_content_response(updated, max_chars=max_chars)


@router.delete("/documents/{document_id}", response_model=DeleteDocumentResponse)
def delete_document(
    document_id: int,
    db: Session = Depends(deps.get_db),
    settings=Depends(deps.get_settings),
    _: bool = Depends(deps.require_admin),
):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    source_id = doc.source_id
    chunk_count = db.scalar(
        select(func.count(Chunk.id)).where(Chunk.document_id == document_id)
    ) or 0
    db.execute(
        delete(Document).where(Document.id == document_id),
        execution_options={"synchronize_session": False},
    )
    audit.record(
        db,
        actor="operator",
        action="delete",
        entity_type="document",
        entity_id=document_id,
        detail={"source_id": source_id, "chunks_deleted": chunk_count},
        enabled=settings.audit_enabled,
    )
    db.commit()
    return DeleteDocumentResponse(
        document_id=document_id,
        source_id=source_id,
        chunks_deleted=chunk_count,
    )
