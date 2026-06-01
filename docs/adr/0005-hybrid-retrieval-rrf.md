# ADR-0005 — Hybrid retrieval: pgvector + full-text, fused with Reciprocal Rank Fusion

- **Status:** Accepted
- **Date:** 2026-06-01
- **Deciders:** project owner
- **Context phase:** Phase 1 (retrieval for `/chat`; reused by `/search` in Phase 2)

## Context

`/chat` must fetch the chunks that ground an answer. The Phase 0 schema carries two
independent signals per chunk: a 384-dim vector (`embeddings.embedding`, HNSW cosine —
ADR-0002) and a generated `tsvector` (`chunks.tsv` = `to_tsvector('english', content)`,
GIN). Semantic search catches paraphrase and meaning; lexical search catches exact terms,
rare tokens, names, and acronyms that an embedding blurs. We want both, combined into one
ranked list, with no managed reranker and no second model resident on the VPS.

The two scores are on different, incomparable scales (cosine similarity ∈ [-1, 1] vs
`ts_rank_cd`, unbounded), so adding or averaging them directly is meaningless.

## Decision

Run the two retrievers independently, then fuse by **rank** (not score) using **Reciprocal
Rank Fusion (RRF)**.

1. **Embed the query** with the *same* local model used at ingest (`all-MiniLM-L6-v2`,
   384-d, normalized). See `implementation-notes.md`: the query is embedded at chat time —
   "embeddings on ingest only" means *no hosted embedding API*, not *never embed a query*.
2. **Vector candidates** (`k_vector = 20`): `ORDER BY embedding <=> :qvec LIMIT 20`,
   restricted to `embeddings.model = :active_model`. Record `vector_score = 1 - (embedding
   <=> :qvec)` (cosine similarity).
3. **Lexical candidates** (`k_fulltext = 20`): `WHERE tsv @@ websearch_to_tsquery('english',
   :q) ORDER BY ts_rank_cd(tsv, q) DESC LIMIT 20`. Record `fulltext_score = ts_rank_cd(...)`.
4. **Fuse**: for a chunk at 1-based rank *r* in a list with weight *w*, add
   `w / (rrf_k + r)`, with `rrf_k = 60`. Sum contributions across the two lists. Default
   weights `w_vector = w_fulltext = 1.0`.
5. **Select** the top `top_k = 8` by fused score as the context set.
6. **Persist** each selected chunk to `retrievals`: `rank` (1..8 by fused score), `score`
   (fused), `vector_score` / `fulltext_score` (the modality scores, `NULL` if that retriever
   didn't surface it), and per-row `method` = `hybrid` if the chunk appeared in *both* lists,
   else `vector` or `fulltext`.

Fusion is a **pure Python function** over the two candidate lists (small lists, trivial
cost, fully unit-testable without a DB). The SQL retrievers return `(chunk_id, score, rank)`.

## Parameters (config-tunable; these are the Phase 1 defaults)

| Knob | Env var | Default |
|---|---|---|
| vector candidate pool | `SECOND_BRAIN_RETRIEVAL_K_VECTOR` | 20 |
| lexical candidate pool | `SECOND_BRAIN_RETRIEVAL_K_FULLTEXT` | 20 |
| RRF constant | `SECOND_BRAIN_RETRIEVAL_RRF_K` | 60 |
| final context size | `SECOND_BRAIN_RETRIEVAL_TOP_K` | 8 |
| vector weight | `SECOND_BRAIN_RETRIEVAL_W_VECTOR` | 1.0 |
| lexical weight | `SECOND_BRAIN_RETRIEVAL_W_FULLTEXT` | 1.0 |

## Consequences

- **Good:** rank-based fusion sidesteps score normalization entirely; a robust default that
  beats either retriever alone on mixed query types; everything stays in one SQL engine — no
  extra infra.
- **Good:** the per-row `method` + modality scores make retrieval explainable and give Phase 3
  eval real data (which modality found the chunk that got cited).
- **Cost:** two indexed queries per turn (one HNSW ANN, one GIN). Negligible at single-user
  scale.
- **Edge cases:** an all-stopword query yields an empty `tsquery` → lexical list empty →
  vector-only (`method='vector'`); an empty corpus → both empty → no context (grounding is
  ADR-0006's job). `rrf_k` and the weights are the **baseline to beat** in the Phase 3 A/B,
  not a permanent freeze.

## Alternatives considered

- **Weighted score fusion (min-max normalize, then blend):** scale-fragile and sensitive to
  per-query outliers. Rejected.
- **Vector-only:** misses exact-term / rare-token matches (names, code, acronyms). Rejected
  as the default.
- **Cross-encoder rerank on top of fusion:** better ranking, but adds a second model and
  latency on the tiny VPS. Deferred to Phase 3 as an eval-gated experiment.
