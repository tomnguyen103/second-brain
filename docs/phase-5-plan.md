# Phase 5 — Daily briefing + scheduled pipelines Implementation Plan

> **For agentic workers:** work TDD (red → green → commit), DRY, YAGNI. Steps use checkbox
> (`- [ ]`) syntax. Pure logic is DB-free unit-tested; the queue/worker/briefing services are
> integration-tested against the real Postgres on 5433; deploy wiring is config, verified to
> parse. Commit after each green task. REQUIRED reading first: `AGENTS.md`, `docs/PROGRESS.md`,
> ADR-0004 (job queue), ADR-0010 (digest/research services this builds on).

**Status: PLAN / not started.** Phase 5 was skipped when the owner jumped 4 → 6; Phase 6 had no
dependency on it. This plan picks up the deferred-to-Phase-5 items and the roadmap's feature #2.

**Goal:** A **morning briefing** you open with coffee, produced by a **scheduled job pipeline**.
Build the durable-job **worker** (ADR-0004's `jobs` table, finally used), a **briefing** that
summarizes what's new since the last one via the `LLMClient`, **stores** it, and surfaces it at
`GET /briefing` + a frontend page. The same worker also runs **async `research_topic`** — closing
the Phase 4 deferral. *Proves (JD): data pipelines, scheduled/production operation, summarization.*

**Scope (v1, MVP-first).** Briefing summarizes **documents ingested since the last briefing** —
it uses only what already exists, no new external inputs. **RSS / GitHub-activity connectors**
(the plan's fuller "scheduled pipelines" vision) and **email delivery** are explicitly a later
increment (see Deferred). v1 delivery is **store-and-display** (no email, no new secret, $0).

**Architecture.** Keep every Phase 1 seam. New logic lives in **services that take a `db`
session** (`app/jobs/*`, `app/briefing/*`), tested with the rolled-back `db_session` fixture; the
worker is a thin dispatch loop over a **handler registry**. The worker builds the embedder/LLM
once (like the MCP tools) and passes them to handlers. `briefing` and `research` are already
allowed `jobs.type` values (Phase 0 schema) — no type migration needed.

**Tech delta:** none new at runtime (no APScheduler — scheduling is OS cron on the one box,
per ADR-0013). New migration `0004` for a `briefings` table. (`uv`-managed venv has no `pip` —
if any dep is ever added, install via `uv pip install`.)

## Decisions (recommended defaults — accept under `/goal`, or override at kickoff; full rationale → ADR-0013)

- **D1 — Worker = poll-based claim with `SELECT … FOR UPDATE SKIP LOCKED`.** Durable (ADR-0004's
  jobs table), restart-safe, concurrency-safe for N workers, and simpler than managing a
  `LISTEN/NOTIFY` connection. `claim_next` filters `status='queued' AND scheduled_at <= now()`,
  flips the row to `running`. *Deferred:* `NOTIFY`-based wake-up as a latency optimization.
- **D2 — Scheduler = OS cron / systemd-timer enqueues the daily `briefing` job.** $0, no resident
  scheduler dependency, fits Compose-on-one-box. The prod stack runs the worker as a `--loop`
  service; a cron line (in the deploy runbook) enqueues the briefing daily. *Rejected:* APScheduler
  (extra resident dep), `pg_cron` (extension install).
- **D3 — Delivery = store-and-display, not email (v1).** Persist briefings; read them at
  `GET /briefing` + a frontend page. *Deferred:* SMTP/email transport — adds a secret + external
  dependency; flag per AGENTS.md cost rule before adding.
- **D4 — Briefing scope (v1) = documents ingested since the last briefing.** `since` = the last
  completed briefing's `period_end` (or, first run, `now - briefing_lookback_hours`). *Deferred:*
  RSS/GitHub pollers as new `sources` — a separate connector increment.
- **D5 — Store briefings in a new `briefings` table (migration 0004).** `(id, generated_at,
  period_start, period_end, summary, body_markdown, document_count, model)`. Honest model + clean
  history query for `/briefing`. *Rejected:* stashing output in `jobs.payload` (opaque) or as a
  `Document` (muddies retrieval).
- **D6 — Async `research_topic` runs through the same worker.** A `research` job calls the existing
  `app/research/service.py`. The inline MCP path stays; the queued path is the async one. Closes
  the ADR-0010 Phase-5 deferral with no new research logic.
- **D7 — `fake` LLM for tests; deterministic.** Briefing summary goes through `LLMClient`; the fake
  driver yields a canned summary (still stored). Real briefings use Gemini. Mirrors ADR-0008.

## File structure (created/modified in this phase)

```text
backend/
  app/
    config.py                      # MODIFY: briefing_lookback_hours, job_max_attempts, worker_poll_seconds
    jobs/__init__.py
    jobs/queue.py                  # CREATE: enqueue / claim_next (FOR UPDATE SKIP LOCKED) / mark_done / mark_failed
    jobs/handlers.py               # CREATE: HANDLERS registry {type -> handler(db, payload, *, embedder, llm)}
    jobs/worker.py                 # CREATE: run_once(db, ...) + loop; __main__ (--once / --loop)
    briefing/__init__.py
    briefing/service.py            # CREATE: build_briefing_messages (pure) + build_briefing(db, llm, *, since)
    db/models.py                   # MODIFY: Briefing model
    schemas/briefing.py            # CREATE: BriefingOut, BriefingListResponse
    api/briefing.py                # CREATE: GET /briefing (latest), GET /briefing/history
    main.py                        # MODIFY: include briefing router
  migrations/versions/0004_briefings.py   # CREATE: briefings table
  tests/
    unit/test_briefing_format.py   # CREATE (DB-free): build_briefing_messages + markdown shape
    integration/test_jobs_queue.py # CREATE: enqueue/claim/done/fail transitions
    integration/test_jobs_worker.py# CREATE: worker runs a handler; failure -> failed + attempts++ + last_error
    integration/test_briefing.py   # CREATE: build_briefing over recent docs; since-filter; empty period
    integration/test_briefing_api.py # CREATE: GET /briefing returns latest via client
deploy/
  docker-compose.prod.yml          # MODIFY: add `worker` service (command: python -m app.jobs.worker --loop)
  runbooks/deploy-checklist.md     # MODIFY: cron line to enqueue the daily briefing
docs/
  adr/0013-briefing-scheduling-and-worker.md  # CREATE
  adr/README.md  PROGRESS.md  implementation-notes.md  # MODIFY
backend/README.md                  # MODIFY: Phase 5 run/verify (enqueue + worker --once; GET /briefing)
```

## Tasks (TDD)

1. **Config + `briefings` table + migration 0004 (DB-bound).** Add `Settings`:
   `briefing_lookback_hours: int = 24`, `job_max_attempts: int = 3`, `worker_poll_seconds: float = 5.0`
   (+ unit test in `test_config_phase6.py` style). Add `Briefing` ORM model + hand-written
   `0004_briefings.py` (match the 0002/0003 style: `GENERATED ALWAYS AS IDENTITY`, index on
   `generated_at`). `alembic upgrade head`. Integration test: a `Briefing` row round-trips.
   Commit `feat(briefing): briefings table + migration 0004 + config`.
2. **Job queue primitives (DB-bound).** `app/jobs/queue.py`: `enqueue(db, *, type, payload=None,
   scheduled_at=None) -> Job`; `claim_next(db, *, types=None, now=None) -> Job | None` using
   `SELECT … WHERE status='queued' AND scheduled_at<=now ORDER BY scheduled_at FOR UPDATE SKIP
   LOCKED LIMIT 1`, then set `status='running'`, `started_at=now`; `mark_done(db, job, result=None)`;
   `mark_failed(db, job, error, *, max_attempts)` → `failed` (or back to `queued` if `attempts <
   max_attempts`). Integration test: enqueue → `claim_next` returns it and flips to `running` so a
   second `claim_next` returns `None`; `mark_done`/`mark_failed` set the right columns + timestamps.
   Commit `feat(jobs): durable queue (claim/done/fail, ADR-0004)`.
3. **Worker dispatch + registry (DB-bound).** `app/jobs/handlers.py`: `HANDLERS: dict[str,
   Callable]` (empty + a test-only registration helper). `app/jobs/worker.py`: `run_once(db, *,
   embedder, llm, max_attempts) -> Job | None` — claim one job, dispatch by type, `mark_done` with
   the handler result or `mark_failed` on exception; `run_loop(...)` polls every
   `worker_poll_seconds`; `__main__` with `--once`/`--loop` building embedder/LLM via `deps`/factory.
   Integration test: register a fake handler, enqueue → `run_once` → `done`; a raising handler →
   `failed`, `attempts` incremented, `last_error` set. Commit `feat(jobs): worker dispatch + handler registry`.
4. **Briefing service (DB-bound + pure).** `build_briefing_messages(period_start, period_end,
   docs) -> list[LLMMessage]` (pure, unit-tested). `build_briefing(db, llm, *, since=None,
   now=None) -> Briefing` — select documents with `created_at` in `(since, now]` (since defaults to
   `now - briefing_lookback_hours`), summarize via `llm.generate`, compose markdown (reuse
   `digest.format_digest` shape), persist a `Briefing`. Zero-new-docs → a valid "nothing new"
   briefing, **no LLM call** (mirrors the chat zero-context short-circuit). Integration: ingest 2
   docs, `build_briefing` → row with summary + `document_count==2`; back-date one doc → `since`
   filter excludes it; empty period → "nothing new", `model is None`. Commit
   `feat(briefing): summarize-new-since service + persistence`.
5. **Briefing job handler (DB-bound).** `handle_briefing(db, payload, *, embedder, llm)` — compute
   `since` from the latest prior `Briefing.period_end` (else lookback), call `build_briefing`,
   return `{briefing_id, document_count}`. Register in `HANDLERS`. Integration via `run_once`:
   enqueue `briefing` → worker produces a `Briefing` row; a second run's `since` picks up where the
   first ended. Commit `feat(briefing): briefing job handler`.
6. **Async research handler (DB-bound).** `handle_research(db, payload, *, embedder, llm)` — calls
   the existing `research.service.research_topic(db, embedder, llm, payload["topic"])`. Register in
   `HANDLERS`. Integration via `run_once`: enqueue `research` (topic) → worker stores a
   `research_note` source that `hybrid_search` then finds. Closes the ADR-0010 deferral. Commit
   `feat(jobs): async research_topic via the worker (closes ADR-0010 deferral)`.
7. **Briefing API (DB-bound).** `app/schemas/briefing.py` (BriefingOut, BriefingListResponse);
   `app/api/briefing.py`: `GET /briefing` (latest, 404 if none), `GET /briefing/history?limit=`.
   Mount in `main.py`. Integration via `client`: after a briefing exists, `/briefing` returns it.
   Commit `feat(api): GET /briefing (latest + history)`.
8. **Deploy wiring (config).** Add a `worker` service to `deploy/docker-compose.prod.yml`
   (`command: ["python","-m","app.jobs.worker","--loop"]`, same env/DSN as `api`, `depends_on` db).
   Add a cron snippet to `docs/runbooks/deploy-checklist.md` that enqueues the daily briefing
   (`docker compose … exec api python -m app.jobs.enqueue briefing` or a tiny enqueue CLI). Validate
   with `docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.prod.example config`.
   Commit `feat(deploy): worker service + daily-briefing cron`.
9. **ADR-0013 + docs (DB-free).** ADR-0013 (worker model, scheduling = OS cron, store-and-display
   delivery, briefings table; D1–D7). README "Phase 5 — run & verify" (enqueue a briefing, run
   `python -m app.jobs.worker --once`, `GET /briefing`). Flip `PROGRESS.md` Phase 5 → ✅ with a dated
   entry; record off-spec calls in `implementation-notes.md`; index ADR-0013. Commit
   `docs: phase-5 ADR-0013 + run/verify + progress`.

## Self-review (against project-plan Phase 5 + JD)
- Scheduled summarization job + morning digest → Tasks 4, 5, 8 ✅
- Durable job pipeline (the `jobs` table finally used) → Tasks 2, 3 (ADR-0004) ✅
- Summarization via `LLMClient` → Task 4 ✅
- Surfaced/shareable (the `/briefing` screenshot) → Task 7 ✅
- Closes the Phase 4 async-research deferral → Task 6 ✅
- Tests alongside code (unit + integration vs real Postgres) → every code task ✅
- $0 / one box (cron scheduler, store-and-display, fake-driver CI) → D2/D3/D7 ✅
- Runnable + documented → Tasks 8, 9 ✅

## Known sharp edges (flagged, not placeholders)
1. **`FOR UPDATE SKIP LOCKED` needs real concurrency to exercise the *skip*.** A single test
   transaction can't simulate two workers (the same txn holds its own lock). Test the **status
   transition** instead (claim flips `queued → running`, so a second `claim_next` filtering
   `status='queued'` returns `None`); document SKIP LOCKED as the N-worker concurrency guard.
2. **Worker commits per job — don't test via the resident loop.** Integration tests call
   `queue.*` / `run_once(db, …)` with the rolled-back `db_session` fixture and assert; never start
   `run_loop` in a test. The `--loop` process is for the deploy stack only.
3. **First-ever briefing has no prior `period_end`.** Fall back to `now - briefing_lookback_hours`;
   cover with a test where no `Briefing` exists yet.
4. **Briefing must not pollute conversation history.** `build_briefing` makes its own `llm.generate`
   call and persists a `Briefing` — never a `Conversation`/`Message` (mirrors the eval read-only rule).
5. **Idempotency of daily enqueue.** Two `briefing` jobs for overlapping periods would double-summarize.
   v1: each briefing's `since` = prior `period_end`, so a re-run over an empty tail yields a "nothing
   new" briefing (cheap, no LLM call) rather than a duplicate — acceptable; note it.
6. **Migration 0004 must be applied live** (`alembic upgrade head`) before the Task 1+ integration
   tests pass, and added to the CI integration job's migrate step (already runs `alembic upgrade head`).
7. **`jobs.type` already allows `briefing`/`research`** (Phase 0 CHECK) — no type migration. `ingest`/
   `embed` handlers are intentionally **out of scope** (inline ingest already covers them).

## Execution handoff
Subagent-driven (recommended) or inline. DB-free tasks (config unit, `build_briefing_messages`,
ADR/docs) run without Docker; everything else needs `docker compose up -d db` + `alembic upgrade
head`. Then PR like prior phases: branch `phase-5-impl`, eval-gated CI must stay green, wait for
CodeRabbit (free tier skips the deep review — see `implementation-notes.md`), merge.
