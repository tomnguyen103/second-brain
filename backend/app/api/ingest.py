import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app import deps
from app.cache.rate_limit import check_rate_limit, client_identity
from app.config import Settings
from app.ingest.parsers import UploadParseError, parse_upload_bytes
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.schemas.ingest import (
    DocumentOut, IngestRequest, IngestResponse, IngestSummary,
)

router = APIRouter(dependencies=[Depends(deps.require_api_access)])
_UPLOAD_SOURCE_TYPES = {"pdf_upload", "file_upload"}


def _enforce_ingest_rate_limit(
    request: Request,
    settings: Settings,
    redis_client,
) -> None:
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


def _to_response(result) -> IngestResponse:
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


def _split_tags(tags: str | None) -> list[str]:
    if not tags:
        return []
    return [tag.strip() for tag in tags.split(",") if tag.strip()]


def _parse_metadata_json(metadata_json: str | None) -> dict:
    if not metadata_json:
        return {}
    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="metadata_json must be valid JSON",
        ) from exc
    if not isinstance(metadata, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="metadata_json must be a JSON object",
        )
    return metadata


def _upload_source_type(requested_type: str | None, extensions: set[str]) -> str:
    source_type = requested_type.strip() if requested_type else None
    if source_type is None:
        return "pdf_upload" if extensions == {".pdf"} else "file_upload"
    if source_type not in _UPLOAD_SOURCE_TYPES:
        allowed = ", ".join(sorted(_UPLOAD_SOURCE_TYPES))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"source_type for uploads must be one of: {allowed}",
        )
    if source_type == "pdf_upload" and extensions != {".pdf"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_type pdf_upload only accepts PDF files",
        )
    return source_type


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    request: Request,
    req: IngestRequest,
    db: Session = Depends(deps.get_db),
    embedder=Depends(deps.get_embedder),
    settings: Settings = Depends(deps.get_settings),
    redis_client=Depends(deps.get_redis),
):
    _enforce_ingest_rate_limit(request, settings, redis_client)

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
    return _to_response(result)


@router.post("/ingest/upload", response_model=IngestResponse)
async def ingest_upload(
    request: Request,
    files: list[UploadFile] = File(...),
    source_name: str = Form(...),
    source_type: str | None = Form(default=None),
    source_uri: str | None = Form(default=None),
    tags: str | None = Form(default=None),
    metadata_json: str | None = Form(default=None),
    db: Session = Depends(deps.get_db),
    embedder=Depends(deps.get_embedder),
    settings: Settings = Depends(deps.get_settings),
    redis_client=Depends(deps.get_redis),
):
    _enforce_ingest_rate_limit(request, settings, redis_client)

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="at least one file is required",
        )
    if len(files) > settings.upload_max_files:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"at most {settings.upload_max_files} files can be uploaded at once",
        )
    clean_source_name = source_name.strip()
    if not clean_source_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_name is required",
        )

    user_metadata = _parse_metadata_json(metadata_json)
    doc_tags = _split_tags(tags)
    parsed_docs: list[DocumentInput] = []
    extensions: set[str] = set()
    for upload in files:
        data = await upload.read(settings.upload_max_bytes + 1)
        await upload.close()
        if len(data) > settings.upload_max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"{upload.filename or 'uploaded file'} exceeds upload_max_bytes",
            )
        try:
            parsed = parse_upload_bytes(
                filename=upload.filename,
                content_type=upload.content_type,
                data=data,
                allowed_extensions=settings.upload_allowed_extensions,
            )
        except UploadParseError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{upload.filename or 'uploaded file'}: {exc}",
            ) from exc

        metadata = dict(parsed.metadata)
        if user_metadata:
            metadata["user_metadata"] = user_metadata
        extensions.add(metadata["upload_extension"])
        parsed_docs.append(
            DocumentInput(
                title=parsed.title,
                content=parsed.content,
                external_id=metadata["original_filename"],
                content_type=parsed.content_type,
                metadata=metadata,
                tags=doc_tags,
            )
        )

    source_spec = SourceSpec(
        type=_upload_source_type(source_type, extensions),
        name=clean_source_name,
        uri=source_uri.strip() if source_uri and source_uri.strip() else None,
        config={
            "upload": {
                "file_count": len(parsed_docs),
                "stored_original_files": False,
                "allowed_extensions": settings.upload_allowed_extensions,
            }
        },
    )
    result = ingest_documents(
        db, embedder, source=source_spec, documents=parsed_docs,
        settings=settings, redis_client=redis_client,
    )
    return _to_response(result)
