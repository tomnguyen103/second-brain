# ADR-0002 — Embeddings: separate table, single fixed model `vector(384)`

- **Status:** Accepted
- **Date:** 2026-06-01
- **Deciders:** project owner
- **Context phase:** Phase 0

## Context

Each chunk needs a vector for ANN search via pgvector. A pgvector column has a **fixed dimension**, so the
storage shape constrains which models we can use and how painful re-embedding is later. The default
embedding model is `sentence-transformers/all-MiniLM-L6-v2` → **384 dimensions**.

## Decision

Store embeddings in a **separate `embeddings` table** (1 row per chunk per model), not as a column on
`chunks`. The vector column is `vector(384)`. A `UNIQUE (chunk_id, model)` constraint allows the same chunk
to carry vectors from more than one model over time, while keeping exactly one row per model.

Index: **HNSW** with `vector_cosine_ops` (cosine distance), matching the normalized sentence-transformer
output.

## Consequences

- **Good:** re-embedding with a future model is an *additive* insert, not a destructive column rewrite.
  Keeps `chunks` narrow (better cache behaviour for retrieval that only needs text + tsv).
- **Good:** HNSW gives strong recall/latency at single-user scale; parameters (`m`, `ef_construction`,
  `ef_search`) are tunable later with an `EXPLAIN ANALYZE` story (Phase 6).
- **Cost:** a join from `chunks` to `embeddings` on the vector path. Negligible at this scale, and the ANN
  index drives the search anyway.
- **Constraint:** if a second model with a *different* dimension is ever adopted, it needs its own column
  or table (a new migration) — `vector(384)` is fixed. Accepted; cross that bridge only if it appears.

## Alternatives considered

- **`chunks.embedding` column:** simplest, one fewer join — but couples re-embedding to the chunk row and
  forces a destructive rewrite to change models. Rejected.
- **IVFFlat index:** lower build cost, but needs a representative training set and tends to lag HNSW on
  recall/latency for small corpora. Rejected as the default; revisit only if HNSW build time bites.
