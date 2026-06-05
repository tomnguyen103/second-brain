"""GET /search — semantic + full-text search over ingested chunks."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import deps
from app.cache.search import get_search_cache, set_search_cache
from app.config import Settings
from app.retrieval.hybrid import hybrid_search, load_display_chunks
from app.schemas.search import SearchHit, SearchResponse

router = APIRouter(dependencies=[Depends(deps.require_api_access)])


@router.get("/search", response_model=SearchResponse)
def search_endpoint(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(8, ge=1, le=50),
    source_ids: list[int] | None = Query(None),
    tags: list[str] | None = Query(None),
    db: Session = Depends(deps.get_db),
    embedder=Depends(deps.get_embedder),
    settings: Settings = Depends(deps.get_settings),
    redis_client=Depends(deps.get_redis),
):
    source_ids_filter = source_ids or None
    tags_filter = tags or None
    cached = get_search_cache(
        redis_client,
        settings,
        query=q,
        top_k=top_k,
        source_ids=source_ids_filter,
        tags=tags_filter,
    )
    if cached is not None:
        return SearchResponse.model_validate(cached)

    hits, meta = hybrid_search(
        db, embedder, settings, q,
        top_k=top_k,
        source_ids=source_ids_filter,
        tags=tags_filter,
        redis_client=redis_client,
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

    response = SearchResponse(query=q, hits=result_hits, retrieval=meta)
    set_search_cache(
        redis_client,
        settings,
        query=q,
        top_k=top_k,
        source_ids=source_ids_filter,
        tags=tags_filter,
        payload=response.model_dump(mode="json"),
    )
    return response
