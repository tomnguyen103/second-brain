"""Vector + full-text candidate queries and hybrid search (ADR-0005)."""
from __future__ import annotations

from dataclasses import dataclass

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Text, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session

from app.config import Settings
from app.retrieval.fusion import Candidate, FusedHit, rrf_fuse

_FILTER = """
  AND (:source_ids IS NULL OR d.source_id = ANY(:source_ids))
  AND (:tags IS NULL OR EXISTS (
        SELECT 1 FROM document_tags dt JOIN tags t ON t.id = dt.tag_id
        WHERE dt.document_id = d.id AND t.name = ANY(:tags)))
"""

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


def hybrid_search(db: Session, embedder, settings: Settings, query: str,
                  *, top_k: int | None = None, source_ids=None, tags=None
                  ) -> tuple[list[FusedHit], dict]:
    qvec = embedder.encode([query])[0]
    common = {"source_ids": source_ids, "tags": tags}
    vec = _candidates(db, _VECTOR_SQL,
                      {**common, "qvec": qvec, "model": embedder.model_name,
                       "k": settings.retrieval_k_vector})
    fts = _candidates(db, _FULLTEXT_SQL,
                      {**common, "q": query, "k": settings.retrieval_k_fulltext})
    hits = rrf_fuse(vec, fts, rrf_k=settings.retrieval_rrf_k,
                    w_vector=settings.retrieval_w_vector,
                    w_fulltext=settings.retrieval_w_fulltext,
                    top_k=top_k or settings.retrieval_top_k)
    meta = {"method": "hybrid", "candidates_vector": len(vec),
            "candidates_fulltext": len(fts), "fused_returned": len(hits)}
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
