# ADR-0013 — Daily briefing: durable worker, OS-cron scheduling, store-and-display

- **Status:** Accepted
- **Date:** 2026-06-02
- **Deciders:** project owner (accepted at recommended defaults under the `/goal` directive)
- **Context phase:** Phase 5 (daily briefing + scheduled pipelines)

## Context

The roadmap's feature is a **morning briefing** you open with coffee, produced by a
**scheduled job pipeline**. This is where ADR-0004's `jobs` table is finally used: a durable
worker drains queued work, a **briefing** summarizes what's new since the last one via the
`LLMClient` and is stored for display, and the same worker runs **async `research_topic`**
(closing the ADR-0010 Phase-5 deferral). It must reuse every Phase 1 seam, stay testable
without the resident loop, cost `$0`, and run as one more container on the single VPS
(ADR-0011). Phase 5 was skipped when the owner jumped 4 → 6; this picks up the deferred items.

## Decision

**D1 — Worker = poll-based claim with `SELECT … FOR UPDATE SKIP LOCKED`.** `claim_next` filters
`status='queued' AND scheduled_at <= now` ordered by `scheduled_at`, flips the row to
`running`. Durable (the `jobs` table is the source of truth), restart-safe, and concurrency-safe
for N workers without a `LISTEN/NOTIFY` connection. The `NOTIFY` wake-up (ADR-0004) is deferred
as a latency optimization — single-user polling every few seconds is plenty.

**D2 — Scheduler = OS cron enqueues the daily `briefing` job.** The prod stack runs the worker
as a `--loop` service; a host cron line (`python -m app.jobs.enqueue briefing`, in the deploy
runbook) enqueues the briefing daily. `$0`, no resident scheduler dependency. *Rejected:*
APScheduler (extra resident dep), `pg_cron` (extension install).

**D3 — Delivery = store-and-display, not email (v1).** Briefings persist to a `briefings`
table; read them at `GET /briefing` (latest) + `GET /briefing/history` and a frontend page.
*Deferred:* SMTP/email transport — adds a secret + external dependency; flag per the AGENTS.md
cost rule before adding.

**D4 — Briefing scope (v1) = documents ingested since the last briefing.** `since` = the latest
prior briefing's `period_end` (first run: `now − briefing_lookback_hours`, default 24h). Window
is `(since, now]` — strictly-greater lower bound so the boundary document already summarized
isn't counted twice. *Deferred:* RSS/GitHub pollers as new `sources` (a connector increment).

**D5 — Store briefings in a new `briefings` table (migration 0004).** `(id, generated_at,
period_start, period_end, summary, body_markdown, document_count, model)`. Honest `model`
(NULL for a "nothing new" briefing) + a clean history query. *Rejected:* stashing output in
`jobs.payload` (opaque) or as a `Document` (muddies retrieval provenance).

**D6 — Async `research_topic` runs through the same worker.** A `research` job calls the
existing `app/research/service.py`. The inline MCP path (ADR-0010) stays; the queued path is the
async one. No new research logic.

**D7 — `fake` LLM for tests; deterministic.** The briefing summary goes through `LLMClient`; the
fake driver yields a canned summary (still stored, `model="fake"`). Real briefings use Gemini.
Mirrors ADR-0008.

**Architecture.** Logic lives in services that take a `db` session (`app/briefing/service.py`,
`app/jobs/queue.py`), tested with the rolled-back `db_session` fixture. The worker
(`app/jobs/worker.py`) is a thin dispatch loop over a handler registry
(`app/jobs/handlers.py`, `type → handler(db, payload, *, embedder, llm)`); it builds the
embedder/LLM once and passes them in (like the MCP tools). `briefing`/`research` are already
allowed `jobs.type` values (Phase 0 CHECK) — no type migration.

## Consequences

- **Good:** every Phase 5 / JD bullet has a home — scheduled summarization job (D2/D4/D5),
  durable pipeline finally exercising the `jobs` table (D1), summarization via `LLMClient`
  (D4/D7), a surfaced/shareable briefing (`GET /briefing`, D3), and the closed async-research
  loop (D6). Verified: 146 backend tests pass; a live `--once` smoke enqueued and produced a
  stored briefing; the prod compose validates with the new `worker` service.
- **Good:** an empty window short-circuits to a "nothing new" briefing with **no LLM call**
  (mirrors the chat zero-context rule), so an accidental double-enqueue over an empty tail is
  cheap and harmless — the idempotency story for the daily schedule.
- **Cost / accepted trade-offs (implementation calls):**
  - **`run_once` is one commit per attempt** (claim → dispatch → mark → commit); queue
    primitives only `flush()`. A handler result is stashed under `payload.result` because the
    `jobs` table has no result column (keeps it inspectable). `build_briefing` flushes; the
    worker owns the commit.
  - **SAVEPOINT around handler dispatch (atomic attempt).** The handler runs inside
    `db.begin_nested()`; on failure the savepoint is rolled back (partial writes discarded)
    before `mark_failed`, while the claim — taken before the savepoint — survives. A failed job
    never commits orphaned rows. The savepoint is managed manually and gated on `is_active` so a
    handler that commits internally (`research_topic` via `ingest_documents`) is tolerated: that
    commit releases the savepoint, so we don't double-release it. Research therefore isn't
    strictly atomic per attempt, but `ingest_documents` dedupes on `content_hash`, so a retry is
    idempotent (the re-run note is a `duplicate`). (Tightened after CodeRabbit review on PR #10.)
  - **Deferred — index on `documents.created_at`.** `build_briefing` range-scans `created_at`;
    fine at personal scale (daily, sub-second seqscan). A composite `(created_at, id)` index
    (migration 0005) is the clean fix if the corpus grows.
  - **`FOR UPDATE SKIP LOCKED` isn't exercised by a single test transaction** (it can't
    simulate two workers). Tests assert the status transition (`queued → running` makes a second
    `claim_next` return `None`); SKIP LOCKED is documented as the N-worker guard. The resident
    `run_loop` is deploy-only and not unit-tested.

## Alternatives considered

- **APScheduler / `pg_cron` for scheduling.** A resident scheduler or a DB extension for one
  daily tick is more moving parts than a cron line on the box. Rejected (D2).
- **`LISTEN/NOTIFY`-driven worker.** Lower latency, but correctness then leans on a held
  connection; polling is simpler and the durable table already guarantees delivery (ADR-0004).
  Kept as a future optimization.
- **Email the briefing in v1.** Adds an SMTP secret + external dependency for no extra signal
  over store-and-display; deferred per the cost rule (D3).
- **Reuse `jobs.payload` or a `Document` to store the briefing.** Opaque / pollutes retrieval;
  a dedicated table is the honest model (D5).
