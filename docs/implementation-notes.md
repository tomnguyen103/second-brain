# Implementation Notes — Second Brain

A running record of decisions, changes, and trade-offs that **weren't in the original
spec** — the "why it ended up like this" you'll want when you (or a reviewer) look back.
Append a dated entry whenever you make a non-obvious call during implementation.

How to use: newest entries on top. For each, note **what**, **why**, and **trade-off /
what I gave up**. Keep it honest — the surprises are the valuable part.

---

## Decisions made during planning (before any code)

These shaped the spec itself and are worth recording, since none were in the very first
"build a personal project" brief.

### LLM driver: Gemini Flash API (free tier), not local-only
- **Why:** keeps the VPS tiny and cheap — no GPU, no model resident 24/7, no per-token
  bill. Free tier (~1,500 req/day) is plenty for one user.
- **Trade-off:** query text + retrieved chunks transit to Google (privacy cost; noted for
  the GDPR story). Mitigation: a local Ollama path kept behind the same `LLMClient`
  interface as a "private mode" — flip by config.

### Runtime: Docker Compose on one VPS, NOT Kubernetes
- **Why:** single-user app; K8s's benefits (multi-node, autoscaling, self-healing) solve
  problems we don't have. Managed K8s would blow the ~$5/mo budget to $70+/mo.
- **Trade-off:** no "runs on K8s in prod" claim. Recovered by making K8s a **learning
  track** (Phase 7) on free local k3s/kind — manifests, HPA, ingress, CI/CD proven and
  screenshotted, then torn down. Judgment ("knew when not to use K8s") is itself a signal.

### Database: self-hosted Postgres as the workhorse, not a managed vector DB
- **Why:** one engine does relational + pgvector + full-text + JSONB + analytics; no extra
  managed-service fee or storage cap; richer SQL/modeling story for the JD.
- **Trade-off:** you operate it yourself (backups, pooling, tuning) — but that's the point
  for the "I can operate Postgres" signal. Redis kept only for caching/rate-limit.

### Research flow: app does its own research; NotebookLM stays manual
- **Why:** Gemini chats emit no events to hook, and NotebookLM has no free API — a
  programmatic chain would be brittle. An in-app "research this topic" MCP tool (Gemini +
  optional web search → summarize → store → auto-ingest) is robust and controllable.
- **Trade-off:** no automatic Gemini-chat → NotebookLM → brain pipe. NotebookLM is used by
  hand for deep study; you paste anything worth keeping into the app's capture path.

### Gemini Ultra subscription ≠ API quota
- **Clarification (not a choice):** the Ultra subscription powers the consumer apps
  (NotebookLM, Gemini app, Antigravity) used by hand; the app's code uses the separate
  free Gemini **API** tier. Don't expect Ultra to raise the API limits.

---

## Implementation-time notes

### 2026-06-01 — Phase 1 implementation fixes (four off-spec corrections)

1. **`tsv` ORM column marked `Computed`** — the `chunks.tsv` column is a PostgreSQL
   `GENERATED ALWAYS AS ... STORED` column. SQLAlchemy didn't know this and included it
   in every `INSERT chunks ...` with `tsv=NULL`, causing `psycopg.errors.GeneratedAlways`.
   Fix: added `Computed("to_tsvector('english', content)", persisted=True)` to the
   `mapped_column` in `app/db/models.py`. *Affects:* `models.py`.

2. **Chunking word-level overlap fallback** — the unit-level overlap step-back in `_pack`
   only works when each sentence/paragraph is smaller than the overlap budget (~18 tokens).
   When every unit is larger (e.g., 101-word paragraphs with an 18-token overlap budget),
   the step-back loop exits immediately and adjacent chunks don't overlap. Fix: after
   `_pack` returns spans, `chunk_text` post-processes them with `_word_overlap_start` to
   enforce overlap at word boundaries. *Affects:* `app/ingest/chunking.py`.

3. **psycopg3 NULL array bind types** — psycopg3 raises `AmbiguousParameter` when a SQL
   parameter that might be NULL is typed as an array (e.g., `source_ids IS NULL OR ...
   ANY(:source_ids)`). Fix: added explicit `bindparam("source_ids", type_=ARRAY(BigInteger))`
   and `bindparam("tags", type_=ARRAY(Text))` to both SQL text objects in `hybrid.py`.
   *Affects:* `app/retrieval/hybrid.py`.

4. **`test_defaults` env isolation** — when the full suite runs with
   `SECOND_BRAIN_LLM_PROVIDER=fake` in the shell (required for integration tests),
   `Settings()` picks it up and `test_defaults` fails. Fix: `monkeypatch.delenv` clears
   the relevant keys so the test sees true defaults. *Affects:* `tests/unit/test_config.py`.

### 2026-06-01 — Docker installed; Phase 0 migration applied live; Docker DB on host port 5433
First run on a box with Docker Desktop (Win 11, WSL2 backend, engine v29.5.2). Closes the
"live migration not applied" gap from the Phase 0 entry below: `alembic upgrade head` ran
against real pgvector for the first time → `0001_baseline (head)`, with **13 relations**
(12 domain tables + `alembic_version`), `vector` 0.8.2, and the `ix_embeddings_hnsw` HNSW
index all verified live.
- **What:** Docker DB published on **host port 5433** (container still 5432). `docker-compose.yml`
  port mapping and `backend/app/config.py` `database_url` default both updated to 5433; the stale
  `backend/.env` (pinned to 5432 from a prior `cp .env.example .env`) was removed so the new
  default applies with no env-var ceremony.
- **Why:** a **native PostgreSQL 16** Windows service (`postgresql-x64-16`) already owns host
  `5432` and was intercepting Alembic's `localhost:5432` connection (peer auth inside the
  container worked, but TCP from the host hit the native server → "password authentication failed
  for user second_brain"). Owner chose to leave the native install running and move the Docker DB.
- **Trade-off / what I gave up:** the canonical `5432` default — a fresh checkout on a machine
  without the clash now also defaults to 5433 (override via `SECOND_BRAIN_DATABASE_URL` or `.env`).
  `backend/.env.example` still references 5432 and is permission-protected from edits in this
  harness; update it to 5433 (or always delete `.env` after copying) to avoid reintroducing the clash.
- **Affects:** `docker-compose.yml`, `backend/app/config.py`, `backend/.env(.example)`, `backend/README.md`.

### 2026-06-01 — Phase 1 plan finalized (ADRs 0005–0007; no code yet)
Under `/goal complete phase 1 plan, and prepare for phase 2`. The owner approved the four
execution forks via the recommended defaults (in-session), so the plan was finalized rather
than waiting on further interactive sign-off. Artifacts: `docs/adr/0005` (hybrid retrieval +
RRF), `0006` (prompt + citation contract), `0007` (Phase 1 API + execution model);
`docs/phase-1-plan.md` (TDD task plan); `docs/phase-2-plan.md` (Phase 2 readiness). **No
application code written** — the "don't scaffold until contracts approved" gate is respected;
the code lives as a reviewable plan, not in `app/`.

Decisions / clarifications worth recording (newest first):
- **Query is embedded at chat time** — what / why: hybrid retrieval needs a query vector, so the
  spec phrase "embeddings on ingest only" is sharpened to *"no hosted embedding API; documents
  are embedded at ingest and the query is embedded at `/chat` with the same local MiniLM model."*
  Trade-off: the ~90 MB MiniLM model is resident in the API process (fine on a 4 GB box).
  Affects: ADR-0005, `embeddings/encoder.py`, `retrieval/hybrid.py`.
- **`raw_text` retained in Phase 1** — what / why: the ER-doc D5 post-embed purge is a Phase 6
  retention concern; keeping `raw_text` now aids debugging/re-chunk. Trade-off: a little extra
  storage until Phase 6 adds the purge. Affects: `ingest/service.py`, Phase 6.
- **Four forks accepted (recommended options):** Python **3.12** venv for the backend (torch has
  no reliable cp314 wheel — the machine already has CPython 3.12.13 via `py`); **Docker Desktop**
  for the test DB (matches `docker-compose.yml`); **inline synchronous ingest** (the `jobs` queue
  / ADR-0004 waits for Phase 5); **non-streaming `/chat`** (SSE deferred to Phase 2). Env check:
  `py --list` shows 3.14 (default) + 3.12.13; `docker` not installed. Affects: ADR-0007,
  `requirements.txt`, `README.md`.
- **Prompt version is a code constant** (`PROMPT_VERSION="rag-v1"`), not persisted per message —
  no column exists; Phase 3 (MLflow) formalizes storage + A/B + rollback. Affects: ADR-0006.
- **Zero-context short-circuit:** when retrieval returns nothing, `/chat` returns a fixed refusal
  and makes **no LLM call** (saves free-tier quota, removes hallucination risk). Affects: ADR-0006,
  `chat/service.py`.
- **`fake` LLM driver** added (config `SECOND_BRAIN_LLM_PROVIDER=fake`) so the whole pipeline is
  testable with no key and no network — also the CI path. Affects: ADR-0007, `llm/fake.py`.

### 2026-06-01 — Phase 0 closed under `/goal end of phase 0` (decisions LOCKED)
The session goal directive said to drive Phase 0 to completion without pausing, so the 5 proposals
below were **accepted at their recommended defaults** rather than waiting for interactive sign-off,
and each is now an ADR (`docs/adr/0002–0004`; D4/D5 captured in the ER doc + this note). If you'd
have chosen differently on any, say so and I'll revise the ADR + migration before Phase 1 builds on it.

Two implementation-time deviations worth recording:
- **Requirements are version *ranges*, not hard pins.** Why: this machine runs Python 3.14 and the
  originally pinned `psycopg-binary==3.2.1` has no 3.14 wheel. Ranges (`alembic>=1.13.2,<2`,
  `SQLAlchemy>=2.0.31,<2.1`, `psycopg[binary]>=3.2.10,<3.4`, `pgvector>=0.3.2,<0.5`,
  `pydantic-settings>=2.3.4,<3`) resolve across 3.11–3.14. *Gave up:* exact reproducibility — re-pin
  to a lockfile once the VPS Python is fixed in Phase 6.
- **Live migration not applied in this environment.** Docker isn't installed on this box, so Phase 0
  was verified *offline*: models import (12 tables on metadata) + `alembic upgrade head --sql` renders
  full DDL. The live `alembic upgrade head` against pgvector is a documented user step
  (backend/README). *Gave up:* an end-to-end "rows in a real DB" proof until Docker is available.

The five schema-shaping calls (now locked):
- **Embeddings as a separate table, `vector(384)`, one model** — keeps re-embedding additive
  (pgvector dims are fixed). *Gave up:* the simplicity of a single `chunks.embedding` column.
- **Chunking ~512 tokens / ~15% overlap, semantic-boundary split** — safe MiniLM-class default.
  *Gave up:* nothing yet; just needs your target size confirmed before ADR-0003.
- **`jobs` table + LISTEN/NOTIFY as wake-up** (not NOTIFY-only) — durable, restart-safe.
  *Gave up:* a bit more infra than pure NOTIFY, in exchange for not losing events.
- **`bigint` identity keys** (not uuid) — smaller/faster for a single-user app.
  *Gave up:* client-generated IDs / row-count opacity (don't need either here).
- **`raw_text` purged after embedding** — supports the retention / delete-my-data story.
  *Gave up:* keeping the original blob around for cheap re-chunking later.
- Affects: Phase 0 migrations, future ADR-0002/0003/0004.

*(Implementation-time notes — newest on top. Template below.)*

<!--
### YYYY-MM-DD — <short title>
- What: 
- Why: 
- Trade-off / what I gave up: 
- Affects: <files / phases>
-->
