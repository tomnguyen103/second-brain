"""GET /search — semantic + full-text search over ingested chunks."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import deps
from app.config import Settings
from app.retrieval.hybrid import hybrid_search, load_display_chunks
from app.schemas.search import SearchHit, SearchResponse

router = APIRouter()


@router.get("/search", response_model=SearchResponse)
def search_endpoint(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(8, ge=1, le=50),
    source_ids: list[int] | None = Query(None),
    tags: list[str] | None = Query(None),
    db: Session = Depends(deps.get_db),
    embedder=Depends(deps.get_embedder),
    settings: Settings = Depends(deps.get_settings),
):
    hits, meta = hybrid_search(
        db, embedder, settings, q,
        top_k=top_k,
        source_ids=source_ids or None,
        tags=tags or None,
    )
    chunk_ids = [h.chunk_id for h in hits]
    display = load_display_chunks(db, chunk_ids)

    result_hits = []
    for h in hits:
        dc = display.get(h.chunk_id)
        if dc is None:
            continue
        result_hits.append(SearchHit(
            chunk_id=h.chunk_id,
            document_id=dc.document_id,
            document_title=dc.document_title,
            source_id=dc.source_id,
            source_name=dc.source_name,
            snippet=dc.content,
            score=h.score,
            vector_score=h.vector_score,
            fulltext_score=h.fulltext_score,
            method=meta["method"],
            char_start=dc.char_start,
            char_end=dc.char_end,
        ))

    return SearchResponse(query=q, hits=result_hits, retrieval=meta)
