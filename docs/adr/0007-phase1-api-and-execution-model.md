# ADR-0007 — Phase 1 API surface and execution model

- **Status:** Accepted
- **Date:** 2026-06-01
- **Deciders:** project owner
- **Context phase:** Phase 1 (the RAG MVP API)

## Context

Phase 1 exposes the RAG MVP as FastAPI endpoints on the Phase 0 schema. We must freeze their
request/response contracts (so the Phase 2 Next.js UI can build against them) and the
execution model: sync vs async, inline vs queued ingest, streaming vs not, and how the LLM
driver is selected. Four forks were decided with the owner, all at the recommended option:
**Python 3.12 venv** runtime, **Docker Desktop** test DB, **inline synchronous ingest**, and
**non-streaming chat**.

## Decision

**Stack.** Synchronous SQLAlchemy 2.0 over psycopg3 (matches the existing
`postgresql+psycopg` URL); FastAPI endpoints; the local embedder and the LLM call run **inline
in the request** (single-user, low concurrency — acceptable; a worker/threadpool is a later
optimization, not MVP scope).

**Driver selection.** `SECOND_BRAIN_LLM_PROVIDER ∈ {gemini, ollama, fake}` (default
`gemini`). A request may set `options.private_mode = true` to force the `ollama` driver for
that one call. `fake` is a deterministic in-process driver (echoes a cited answer built from
the context) for tests / CI / offline smoke — **no network, no key**.

### `POST /ingest` — inline synchronous

Find-or-create the `source` by `(type, name)`; per document: normalize → `content_hash`;
dedupe on `UNIQUE(source_id, content_hash)` (skip + report duplicates); chunk (ADR-0003) →
embed (local) → insert `documents` / `chunks` / `embeddings`; set `status='embedded'`,
`ingested_at = now()`. `raw_text` is **retained** in Phase 1 (the post-embed purge — ER-doc
D5 — lands in Phase 6). A per-document failure is captured as `status='failed'` and reported;
it does **not** fail the whole request.

```json
// Request
{
  "source": { "type": "manual", "name": "My Notes", "uri": null, "config": {} },
  "documents": [
    { "title": "HNSW tuning notes", "content": "full raw text …",
      "external_id": null, "content_type": "text/markdown",
      "metadata": { "author": "me" }, "tags": ["ml", "postgres"] }
  ]
}
```
```json
// Response
{
  "source_id": 1,
  "documents": [
    { "document_id": 10, "title": "HNSW tuning notes", "status": "embedded",
      "content_hash": "9f2…", "chunk_count": 7, "embedded_count": 7, "duplicate_of": null }
  ],
  "summary": { "received": 1, "embedded": 1, "duplicates": 0, "failed": 0, "chunks_created": 7 }
}
```
`status` ∈ `embedded | duplicate | failed`. On `duplicate`, `duplicate_of` is the existing
`document_id` and chunk counts are 0.

### `POST /chat` — non-streaming JSON

Find/create conversation → persist user message → hybrid retrieve (ADR-0005) → build prompt
(ADR-0006) → generate via `LLMClient` → persist assistant message (`model`, `token_usage`,
`latency_ms`) + `retrievals` rows → return answer + citations.

```json
// Request
{
  "message": "What did I note about HNSW tuning?",
  "conversation_id": null,
  "top_k": 8,
  "filters": { "source_ids": [1], "tags": ["ml"] },
  "options": { "private_mode": false, "include_chunks": true }
}
```
```json
// Response
{
  "conversation_id": 5,
  "message_id": 42,
  "answer": "You compared m and ef_construction … [1][2]",
  "citations": [
    { "marker": 1, "chunk_id": 100, "document_id": 10, "document_title": "HNSW tuning notes",
      "source_id": 1, "source_name": "My Notes", "snippet": "…the relevant span…",
      "score": 0.0312, "vector_score": 0.81, "fulltext_score": 0.55, "method": "hybrid",
      "char_start": 1200, "char_end": 1712 }
  ],
  "usage": { "prompt_tokens": 950, "completion_tokens": 120, "total_tokens": 1070 },
  "model": "gemini-1.5-flash",
  "latency_ms": 1430,
  "retrieval": { "method": "hybrid", "candidates_vector": 20, "candidates_fulltext": 20,
                 "fused_returned": 8 }
}
```
`citations[].snippet` and `char_start/end` are included only when `options.include_chunks` is
true. On the zero-context path (ADR-0006), `answer` is the fixed refusal, `citations` is `[]`,
`model` is `null`.

### `GET /health`

`{ "status": "ok", "db": "ok|down", "embedder": "loaded|unloaded" }` for readiness.

**Cross-cutting.** Pydantic v2 schemas; permissive CORS for `http://localhost:3000` (the
Phase 2 dev origin); `422` on validation error, `400` on empty/oversized input, `500` with a
safe message on embed/LLM failure.

## Consequences

- **Good:** the smallest thing that's fully runnable and demoable end-to-end; trivially
  curl-/test-able; contracts are frozen, so Phase 2 can start in parallel.
- **Good:** the `fake` driver makes the entire pipeline testable with no external dependency —
  also the CI path.
- **Cost:** a large ingest blocks its request while embedding. Acceptable for a personal
  corpus; the durable `jobs` table (ADR-0004) is the escape hatch when Phase 5 needs
  async/scheduled work.
- **Constraint:** inline embedding loads MiniLM into the API process (~90 MB resident) — fine
  on a 4 GB box.

## Alternatives considered

- **Async SQLAlchemy/endpoints:** more scalable, but adds complexity the single-user workload
  doesn't need. Rejected for Phase 1.
- **Job-queued ingest now:** exercises ADR-0004 immediately but adds a worker + status polling
  to the MVP. Deferred to Phase 5, where scheduled work makes it pay off.
- **Streaming chat (SSE):** better UX, but harder to build/test headless; the Next.js UI
  (Phase 2) is the right home. Deferred.
