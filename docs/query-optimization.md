# Query optimization — EXPLAIN ANALYZE before/after (Phase 6)

The two hot retrieval paths (ADR-0005) are vector KNN (pgvector HNSW) and lexical search
(Postgres full-text + GIN). This documents the index strategy with **measured** `EXPLAIN
(ANALYZE, BUFFERS)` numbers and the tuning knobs that trade recall against latency.

> **Method.** The fixed eval corpus is tiny (~12 chunks), and at that size Postgres correctly
> prefers a sequential scan — an index only earns its keep once the table grows. To measure the
> indexes honestly we inflated each table to a realistic size **inside a transaction, ran the
> plans, then `ROLLBACK`** (so the dev DB is untouched and nothing synthetic is committed).
> Numbers below are from the local pgvector-backed Docker database on host port 5433.

## 1. Vector KNN — HNSW (`ix_embeddings_hnsw`, `vector_cosine_ops`)

Query (the candidate query from `app/retrieval/hybrid.py`), `LIMIT 8`, table inflated to ~2,012
embeddings:

| Plan | Node | Execution time | Shared buffers |
|---|---|---|---|
| **After** (HNSW enabled) | `Index Scan using ix_embeddings_hnsw` | **0.088 ms** | 134 |
| **Before** (HNSW disabled → exact) | `Seq Scan` + top-N heapsort over 2,012 rows | **0.706 ms** | 407 |

```
-- After (index used):
Limit (actual time=0.061..0.067 rows=8)
  ->  Index Scan using ix_embeddings_hnsw on embeddings (actual time=0.060..0.065 rows=8)
        Order By: (embedding <=> '[...]'::vector)
 Execution Time: 0.088 ms

-- Before (SET enable_indexscan=off; exact KNN):
Limit (actual time=0.698..0.699 rows=8)
  ->  Sort (Sort Method: top-N heapsort)
        ->  Seq Scan on embeddings (actual time=0.003..0.589 rows=2012)
 Execution Time: 0.706 ms
```

**Takeaway:** HNSW returns the top-8 by reading ~8 rows instead of sorting all 2,012 — **~8×
faster** and ~3× fewer buffer reads at this size, and the gap widens as the table grows (exact
scan is O(n), HNSW ~O(log n)). HNSW is approximate, so the trade-off is recall vs latency:
`SET hnsw.ef_search` (default 40) raises recall at the cost of latency; index build is tuned
with `m` / `ef_construction` (ADR-0002). Cosine ops match the normalized MiniLM embeddings.

## 2. Lexical search — GIN on the generated `tsv` (`ix_chunks_tsv`)

Query (the full-text candidate query), `websearch_to_tsquery('english', 'hnsw tuning')`,
`LIMIT 8`, table inflated to ~30,025 chunks (≈26 matching):

| Plan | Node | Execution time |
|---|---|---|
| **After** (GIN enabled) | `Bitmap Index Scan on ix_chunks_tsv` → Bitmap Heap Scan (Heap Blocks: exact=9) | **0.436 ms** |
| **Before** (GIN disabled) | `Seq Scan` over 30,025 rows | **2.340 ms** |

```
-- After (index used):
  ->  Bitmap Heap Scan on chunks c (actual time=0.377..0.416 rows=26)
        Recheck Cond: (tsv @@ '''hnsw'' & ''tune'''::tsquery)
        Heap Blocks: exact=9
        ->  Bitmap Index Scan on ix_chunks_tsv (actual time=0.367..0.367 rows=49)
 Execution Time: 0.436 ms

-- Before (SET enable_bitmapscan=off; enable_indexscan=off):
  ->  Seq Scan on chunks c (actual time=0.007..2.327 rows=26)
 Execution Time: 2.340 ms
```

**Takeaway:** the GIN bitmap index scan touches **9 heap blocks** instead of scanning all
30,025 rows — **~5.4× faster**, and the ratio grows with corpus size. The `tsv` column is
`GENERATED ALWAYS … STORED` so the index stays in sync with `content` automatically (no
trigger to drift). `ts_rank_cd` ranking runs only over the ~26 matched rows, not the whole
table.

## Tuning knobs (summary)

| Knob | Effect | Default here |
|---|---|---|
| `hnsw.ef_search` | ↑ recall, ↑ latency for vector search | 40 (pgvector default) |
| HNSW `m` / `ef_construction` | build-time recall/space vs build time (ADR-0002) | pgvector defaults |
| `work_mem` | larger sorts/hashes stay in memory | Postgres default |
| RRF `k`, `top_k`, per-modality `k` | candidate breadth before fusion (ADR-0005) | `rrf_k=60`, `top_k=8`, `k=20` |

## How to reproduce

Bring the DB up (`docker compose up -d db`), then run the inflate-measure-rollback scripts
described above against `psql`. Because every experiment ends in `ROLLBACK`, it is safe to run
repeatedly without seeding the database. At production scale the planner chooses both indexes
without coaxing; the `enable_*=off` toggles above only exist to show the exact-scan baseline.
