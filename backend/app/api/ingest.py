from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import deps
from app.cache.rate_limit import check_rate_limit, client_identity
from app.config import Settings
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.schemas.ingest import (
    DocumentOut, IngestRequest, IngestResponse, IngestSummary,
)

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    request: Request,
    req: IngestRequest,
    db: Session = Depends(deps.get_db),
    embedder=Depends(deps.get_embedder),
    settings: Settings = Depends(deps.get_settings),
    redis_client=Depends(deps.get_redis),
):
    decision = check_rate_limit(
        redis_client,
        settings,
        bucket="ingest",
        identity=client_identity(request),
        limit=settings.ingest_rate_limit_requests,
        window_seconds=settings.ingest_rate_limit_window_seconds,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="ingest rate limit exceeded",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )

    source_spec = SourceSpec(
        type=req.source.type,
        name=req.source.name,
        uri=req.source.uri,
        config=req.source.config,
    )
    doc_inputs = [
        DocumentInput(
            title=d.title,
            content=d.content,
            external_id=d.external_id,
            content_type=d.content_type,
            metadata=d.metadata,
            tags=d.tags,
        )
        for d in req.documents
    ]
    result = ingest_documents(
        db, embedder, source=source_spec, documents=doc_inputs,
        settings=settings, redis_client=redis_client,
    )

    docs_out = [
        DocumentOut(
            document_id=dr.document_id,
            title=dr.title,
            status=dr.status,
            content_hash=dr.content_hash,
            chunk_count=dr.chunk_count,
            embedded_count=dr.embedded_count,
            duplicate_of=dr.duplicate_of,
            error=dr.error,
        )
        for dr in result.documents
    ]
    summary = IngestSummary(
        received=len(result.documents),
        embedded=sum(1 for d in result.documents if d.status == "embedded"),
        duplicates=sum(1 for d in result.documents if d.status == "duplicate"),
        failed=sum(1 for d in result.documents if d.status == "failed"),
        chunks_created=sum(d.chunk_count for d in result.documents),
    )
    return IngestResponse(source_id=result.source_id, documents=docs_out, summary=summary)
