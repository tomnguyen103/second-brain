"""Reciprocal Rank Fusion of two candidate lists — ADR-0005."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Candidate:
    chunk_id: int
    score: float       # modality score: cosine similarity OR ts_rank_cd
    rank: int          # 1-based within its list


@dataclass
class FusedHit:
    chunk_id: int
    score: float                       # fused RRF score
    method: str                        # vector | fulltext | hybrid
    vector_score: float | None = None
    fulltext_score: float | None = None
    rank: int = 0                       # 1-based, set after sort


def rrf_fuse(vector: list[Candidate], fulltext: list[Candidate], *,
             rrf_k: int = 60, w_vector: float = 1.0, w_fulltext: float = 1.0,
             top_k: int = 8) -> list[FusedHit]:
    vmap = {c.chunk_id: c for c in vector}
    fmap = {c.chunk_id: c for c in fulltext}
    fused: dict[int, float] = {}
    for c in vector:
        fused[c.chunk_id] = fused.get(c.chunk_id, 0.0) + w_vector / (rrf_k + c.rank)
    for c in fulltext:
        fused[c.chunk_id] = fused.get(c.chunk_id, 0.0) + w_fulltext / (rrf_k + c.rank)

    hits: list[FusedHit] = []
    for cid, s in fused.items():
        in_v, in_f = cid in vmap, cid in fmap
        method = "hybrid" if in_v and in_f else ("vector" if in_v else "fulltext")
        hits.append(FusedHit(
            chunk_id=cid, score=s, method=method,
            vector_score=vmap[cid].score if in_v else None,
            fulltext_score=fmap[cid].score if in_f else None,
        ))
    hits.sort(key=lambda h: (h.score, h.chunk_id), reverse=True)
    hits = hits[:top_k]
    for i, h in enumerate(hits, start=1):
        h.rank = i
    return hits
