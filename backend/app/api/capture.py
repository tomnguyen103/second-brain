from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import deps
from app.cache.rate_limit import check_rate_limit, client_identity
from app.capture.service import capture_page
from app.config import Settings
from app.schemas.capture import CaptureRequest, CaptureResponse
from app.schemas.ingest import DocumentOut, IngestSummary


router = APIRouter(dependencies=[Depends(deps.require_api_access)])


@router.post("/capture", response_model=CaptureResponse)
def capture(
    request: Request,
    req: CaptureRequest,
    db: Session = Depends(deps.get_db),
    embedder=Depends(deps.get_embedder),
    settings: Settings = Depends(deps.get_settings),
    redis_client=Depends(deps.get_redis),
):
    decision = check_rate_limit(
        redis_client,
        settings,
        bucket="ingest",
        identity=client_identity(request, settings),
        limit=settings.ingest_rate_limit_requests,
        window_seconds=settings.ingest_rate_limit_window_seconds,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="ingest rate limit exceeded",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )

    try:
        result = capture_page(
            db,
            embedder,
            settings,
            req,
            redis_client=redis_client,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    doc = result.ingest.documents[0]
    return CaptureResponse(
        source_id=result.ingest.source_id,
        capture_url=result.capture_url,
        document=DocumentOut(
            document_id=doc.document_id,
            title=doc.title,
            status=doc.status,
            content_hash=doc.content_hash,
            chunk_count=doc.chunk_count,
            embedded_count=doc.embedded_count,
            duplicate_of=doc.duplicate_of,
            error=doc.error,
        ),
        summary=IngestSummary(
            received=len(result.ingest.documents),
            embedded=sum(1 for d in result.ingest.documents if d.status == "embedded"),
            duplicates=sum(1 for d in result.ingest.documents if d.status == "duplicate"),
            failed=sum(1 for d in result.ingest.documents if d.status == "failed"),
            chunks_created=sum(d.chunk_count for d in result.ingest.documents),
        ),
    )
