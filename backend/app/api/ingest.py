from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import deps
from app.config import Settings
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.schemas.ingest import (
    DocumentOut, IngestRequest, IngestResponse, IngestSummary,
)

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    req: IngestRequest,
    db: Session = Depends(deps.get_db),
    embedder=Depends(deps.get_embedder),
    settings: Settings = Depends(deps.get_settings),
):
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
    result = ingest_documents(db, embedder, source=source_spec, documents=doc_inputs)

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
