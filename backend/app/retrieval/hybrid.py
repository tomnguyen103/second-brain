"""Vector + full-text candidate queries and hybrid search (ADR-0005)."""
from __future__ import annotations

from dataclasses import dataclass
import re

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Text, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session

from app.cache.embedding import encode_with_cache
from app.config import Settings
from app.retrieval.fusion import Candidate, FusedHit, rrf_fuse

_FILTER = """
  AND (:source_ids IS NULL OR d.source_id = ANY(:source_ids))
  AND (:tags IS NULL OR EXISTS (
        SELECT 1 FROM document_tags dt JOIN tags t ON t.id = dt.tag_id
        WHERE dt.document_id = d.id AND t.name = ANY(:tags)))
"""
_KEYWORD_STOPWORDS = {
    "about", "after", "also", "and", "anything", "are", "can", "could", "does",
    "for", "from", "how", "into", "not", "nothing", "setup", "someone",
    "something", "somewhere", "that", "the", "then", "this", "what", "when",
    "where", "which", "with", "workflow", "your",
}
_KEYWORD_KEEP = {"workflow"}
_KEYWORD_RE = re.compile(r"[^\W_]{3,}", re.UNICODE)

_VECTOR_SQL = text(f"""
    SELECT e.chunk_id AS chunk_id,
           1 - (e.embedding <=> :qvec) AS score,
           row_number() OVER (ORDER BY e.embedding <=> :qvec) AS rank
    FROM embeddings e
    JOIN chunks c    ON c.id = e.chunk_id
    JOIN documents d ON d.id = c.document_id
    WHERE e.model = :model {_FILTER}
    ORDER BY e.embedding <=> :qvec
    LIMIT :k
""").bindparams(
    bindparam("qvec", type_=Vector(384)),
    bindparam("source_ids", type_=ARRAY(BigInteger)),
    bindparam("tags", type_=ARRAY(Text)),
)

_FULLTEXT_SQL = text(f"""
    SELECT c.id AS chunk_id,
           ts_rank_cd(c.tsv, query) AS score,
           row_number() OVER (ORDER BY ts_rank_cd(c.tsv, query) DESC) AS rank
    FROM chunks c
    JOIN documents d ON d.id = c.document_id,
         websearch_to_tsquery('english', :q) query
    WHERE c.tsv @@ query {_FILTER}
    ORDER BY score DESC
    LIMIT :k
""").bindparams(
    bindparam("source_ids", type_=ARRAY(BigInteger)),
    bindparam("tags", type_=ARRAY(Text)),
)

_KEYWORD_FALLBACK_SQL = text(f"""
    WITH terms AS (
        SELECT lower(unnest(:terms)) AS term
    ),
    scored AS (
        SELECT c.id AS chunk_id,
               sum(
                   CASE WHEN lower(d.title) LIKE ('%' || terms.term || '%') THEN 3 ELSE 0 END
                 + CASE WHEN lower(s.name) LIKE ('%' || terms.term || '%') THEN 2 ELSE 0 END
                 + CASE WHEN lower(c.content) LIKE ('%' || terms.term || '%') THEN 1 ELSE 0 END
               )::float AS score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        JOIN sources s ON s.id = d.source_id
        JOIN terms ON (
            lower(c.content) LIKE ('%' || terms.term || '%')
            OR lower(d.title) LIKE ('%' || terms.term || '%')
            OR lower(s.name) LIKE ('%' || terms.term || '%')
        )
        WHERE 1=1 {_FILTER}
        GROUP BY c.id
    )
    SELECT chunk_id,
           score,
           row_number() OVER (ORDER BY score DESC, chunk_id ASC) AS rank
    FROM scored
    ORDER BY score DESC, chunk_id ASC
    LIMIT :k
""").bindparams(
    bindparam("terms", type_=ARRAY(Text)),
    bindparam("source_ids", type_=ARRAY(BigInteger)),
    bindparam("tags", type_=ARRAY(Text)),
)


@dataclass
class DisplayChunk:
    chunk_id: int
    content: str
    document_id: int
    document_title: str
    source_id: int
    source_name: str
    char_start: int | None
    char_end: int | None


def _candidates(db: Session, sql, params) -> list[Candidate]:
    return [Candidate(int(r.chunk_id), float(r.score), int(r.rank))
            for r in db.execute(sql, params).all()]


def _keyword_terms(query: str) -> list[str]:
    seen: list[str] = []
    for token in _KEYWORD_RE.findall((query or "").lower()):
        if token in _KEYWORD_STOPWORDS and token not in _KEYWORD_KEEP:
            continue
        if token not in seen:
            seen.append(token)
    return seen[:8]


def hybrid_search(db: Session, embedder, settings: Settings, query: str,
                  *, top_k: int | None = None, source_ids=None, tags=None,
                  redis_client=None,
                  ) -> tuple[list[FusedHit], dict]:
    qvec = encode_with_cache(
        embedder,
        [query],
        redis_client=redis_client,
        settings=settings,
        namespace="query",
    )[0]
    common = {"source_ids": source_ids, "tags": tags}
    vec_raw = _candidates(db, _VECTOR_SQL,
                          {**common, "qvec": qvec, "model": embedder.model_name,
                           "k": settings.retrieval_k_vector})
    min_vector = settings.retrieval_min_vector_score
    vec = [c for c in vec_raw if c.score >= min_vector]
    strict_fts = _candidates(db, _FULLTEXT_SQL,
                             {**common, "q": query, "k": settings.retrieval_k_fulltext})
    keyword_terms = _keyword_terms(query)
    keyword_fts = (
        _candidates(db, _KEYWORD_FALLBACK_SQL,
                    {**common, "terms": keyword_terms, "k": settings.retrieval_k_fulltext})
        if not strict_fts and keyword_terms else []
    )
    fts = strict_fts or keyword_fts
    hits = rrf_fuse(vec, fts, rrf_k=settings.retrieval_rrf_k,
                    w_vector=settings.retrieval_w_vector,
                    w_fulltext=settings.retrieval_w_fulltext,
                    top_k=top_k or settings.retrieval_top_k)
    meta = {"method": "hybrid", "candidates_vector": len(vec),
            "candidates_vector_raw": len(vec_raw),
            "vector_filtered_below_threshold": len(vec_raw) - len(vec),
            "min_vector_score": min_vector,
            "candidates_fulltext": len(fts),
            "candidates_fulltext_strict": len(strict_fts),
            "candidates_keyword_fallback": len(keyword_fts),
            "keyword_fallback_used": bool(keyword_fts),
            "fused_returned": len(hits)}
    if (vec_raw or fts) and not hits:
        meta["weak_context"] = True
    return hits, meta


def load_display_chunks(db: Session, chunk_ids: list[int]) -> dict[int, DisplayChunk]:
    if not chunk_ids:
        return {}
    rows = db.execute(text("""
        SELECT c.id, c.content, c.char_start, c.char_end,
               d.id AS document_id, d.title AS document_title,
               s.id AS source_id, s.name AS source_name
        FROM chunks c JOIN documents d ON d.id = c.document_id
                      JOIN sources s   ON s.id = d.source_id
        WHERE c.id = ANY(:ids)
    """), {"ids": chunk_ids}).all()
    return {r.id: DisplayChunk(r.id, r.content, r.document_id, r.document_title,
                               r.source_id, r.source_name, r.char_start, r.char_end)
            for r in rows}
