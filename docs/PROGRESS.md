# Progress Log — Second Brain

Running log of what's done, in progress, and next. Keep this current at the end of each
session — the master prompt treats it as the source of truth for "where we are."

## Status at a glance

| Phase | Description | Status |
|---|---|---|
| Planning | Project design, stack, cost model, roadmap | ✅ Complete |
| 0 | Data model + ER diagram + Alembic migrations + pgvector/full-text indexes | ✅ Complete |
| 1 | RAG MVP: FastAPI /ingest + /chat, hybrid retrieval, Gemini via LLMClient | ✅ Complete |
| 2 | Next.js chat UI (citations, semantic search, feedback; streaming deferred) | ✅ Complete |
| 3 | Evaluation + MLOps: eval set, MLflow, A/B, prompt versioning + rollback | ✅ Complete |
| 4 | MCP server + agentic actions incl. self-research tool | ✅ Complete |
| 5 | Daily briefing + scheduled pipelines | ⬜ Not started |
| 6 | Productionize on VPS + data-ops hardening | ⬜ Not started |
| 7 | Kubernetes learning track on local k3s/kind | ⬜ Not started |

Legend: ⬜ not started · 🟡 in progress · ✅ complete

## Session log

Add a dated entry per working session. Most recent on top.

### 2026-06-02 — Phase 4 COMPLETE: MCP server + agentic actions (incl. self-research)
- **Branch:** `phase-4-impl` (off main, Phase 3 merged via PR #7). Plan in `docs/phase-4-plan.md`;
  decision in ADR-0010.
- **What shipped:** an **MCP server** (`app/mcp_server.py`, FastMCP/stdio, `python -m app.mcp_server`)
  exposing five tools — `search_notes` (hybrid retrieval), `create_task`/`list_tasks` (new `tasks`
  table, migration `0002`), `send_digest` (markdown digest of recent activity), and the flagship
  `research_topic` (LLM writes a note → stored as a `research_note` source → auto-ingested → searchable).
  Logic lives in tested services (`app/{tasks,digest,research}`); tools are thin session-opening wrappers.
- **Verified:** backend `pytest` **78 passed** (unit + integration vs live DB on 5433, fake LLM). Live
  smoke: `search_notes("HNSW index tuning")` → top hit "HNSW index tuning"; `send_digest()` → digest with
  counts. MCP `list_tools()` returns the five tools.
- **DB:** migration `0002_tasks` applied live (`alembic upgrade head`). `tasks` table added.
- **Deferred (per ADR-0010):** async research via the `jobs` queue + optional web search (Phase 5);
  digest *delivery* / email transport (Phase 5/6); SSE transport (stdio is the local-client path).
- **Next:** Phase 5 — daily briefing + scheduled pipelines (the `jobs` table + `briefing`/`research` job
  types are already in the schema).

### 2026-06-02 — Phase 3 COMPLETE: evaluation + MLOps (eval set, MLflow, A/B, prompt versioning)
- **Branch:** `phase-3-impl` (off main, which now has Phase 2 merged via PR #6). Planned in
  `docs/phase-3-plan.md`; decisions in ADR-0008 (eval methodology + MLflow) and ADR-0009 (prompt
  versioning + A/B + rollback).
- **What shipped (`backend/app/eval/` + `backend/eval/`):** a fixed eval set (6-topic markdown
  corpus + 13-case `dataset.yaml`, incl. a multi-source case and one off-corpus refusal); a pure
  metrics module (retrieval hit@k/recall@k/MRR, citation validity, keyword recall, refusal
  correctness, latency p50/p95); a **read-only** eval pipeline + harness (reuses `hybrid_search` +
  versioned `build_messages` + `LLMClient`, persists nothing); MLflow logging to a **local file
  store** (`file:./mlruns`, no server, $0); a runner CLI (`python -m app.eval.runner --configs …`)
  that ingests the corpus, runs each config, logs an MLflow run, and prints an A/B table.
- **Prompt versioning + rollback (ADR-0009):** `app/chat/prompt.py` now has a `PromptSpec` registry
  (`rag-v1` kept byte-for-byte, `rag-v2` variant); `build_messages`/chat select
  `settings.prompt_version`; rollback = set `SECOND_BRAIN_PROMPT_VERSION` back. A/B configs:
  `baseline`/`variant` (deterministic, fake) and `gemini`/`gemini-v2` (real prompt A/B).
- **Verified:** backend `pytest` **64 passed** (unit + integration vs live DB on 5433). Live A/B
  run (`baseline,variant`, real MiniLM embedder + fake LLM) logged 2 MLflow runs and printed the
  table: **hit@k = recall@k = 1.000, MRR ≈ 0.917, citation_validity = 1.000, refusal_accuracy =
  0.923**. `keyword_recall`/`latency` are ~0 on the fake driver by design (D2/ADR-0008) — the real
  numbers come from the documented `gemini` run.
- **Verification caught + fixed:** the eval runner writes the corpus into the shared dev/test DB,
  which broke `test_retrieval` (its "HNSW tuning" query also matched the new eval HNSW note). Fixed
  by scoping the retrieval tests to their own `source_ids` — the right isolation pattern for a
  shared DB. Detail in `implementation-notes.md`.
- **Deferred (per ADR-0008):** LLM-as-judge grading; richer/larger corpus; remote MLflow server
  (Phase 6). **Note:** the runner seeds an "Eval Corpus" source into the dev DB (idempotent; like
  the Phase 2 smoke seed) and writes `./mlruns` (gitignored).
- **Next:** Phase 4 — MCP server + agentic actions (create task, send digest, search, research-this-topic).

### 2026-06-02 — Phase 2 COMPLETE: verified end-to-end + history-citation fix
- **Branch:** `phase-2-impl`. Verified Phase 2 against its Definition of Done before flipping
  status to ✅ — ran the commands, didn't trust the prior log.
- **Static gates (all green):** backend `pytest` **37 passed** (was 36; +1 new test); frontend
  `tsc --noEmit` exit 0; `next build` exit 0 (`/chat` + `/search` static).
- **Live E2E (real DB on 5433, `fake` LLM for determinism):** ingest→`/search` (5 ranked hybrid
  hits)→`/chat` (answer with clickable `[1][2]` → CitationCard showing title/source/snippet/method/
  score)→`/feedback` (201). Conversation sidebar loads live `/conversations`; dark mode works.
- **Gap found & fixed during verification:** replaying a past conversation from the sidebar
  rendered **dead, non-clickable `[n]` markers** and dropped the feedback/source/latency footer —
  because `GET /conversations/{id}` returned raw `retrievals` (chunk_id/rank/score) but not
  reconstructed `citations`, and the chat page mapped history to `{role, content}` only. Fixed:
  the detail endpoint now reconstructs `citations` (marker→document/source/snippet, mirroring
  `chat.service`'s marker logic via `parse_citations` + `load_display_chunks`); the chat page
  rehydrates the live-chat shape so replayed turns get clickable citations + working thumbs.
  Verified live: conversation #34 replay shows 2 clickable cards + feedback "Saved". Detail in
  `implementation-notes.md`.
- **Files:** `backend/app/api/conversations.py`, `backend/app/schemas/conversations.py`,
  `backend/tests/integration/test_search.py` (new test), `frontend/app/chat/page.tsx`,
  `frontend/lib/api/types.ts`. (Plus the prior uncommitted `ConversationSidebar.tsx` dark-mode fix.)
- **Deferred (not blockers, per DoD):** SSE streaming; `npm run gen-types` (hand-written
  `types.ts` intentionally diverges from openapi-typescript's `paths`/`components` shape — running
  codegen would break current imports); feedback analytics (Phase 3/6); auth/deploy (Phase 6).
- **Note:** live smoke seeded the dev DB with a `Phase2 Verify Seed` source + conversations
  #34/#35 + feedback rows (harmless on dev; not committed).
- **Next:** Phase 3 — Evaluation + MLOps (eval set, MLflow harness, A/B, prompt versioning + rollback).

### 2026-06-01 — Phase 2 IN PROGRESS: backend deltas + Next.js UI scaffold
- **Branch:** `phase-2-impl` (off main, which now has Phase 1 merged).
- **Backend deltas shipped:** `GET /search` (hybrid_search wrapper), `GET /conversations`,
  `GET /conversations/{id}`, `POST /feedback` — all with Pydantic v2 schemas + integration tests.
- **Frontend scaffold shipped:** Next.js 16 + TypeScript + Tailwind v4 + shadcn/ui + TanStack Query.
  Routes: `/chat` (message → cited answer → [n] → CitationCard popover; SourceFilter; conversation
  history load), `/search` (full-text+vector results with source/tag filters). Conversation sidebar
  with 15s auto-refresh. Private-mode toggle. Feedback thumbs per message.
- **Build status:** `tsc --noEmit` clean; `next build` clean (both routes static-generate).
- **Open decisions resolved:** non-streaming first; openapi-typescript codegen script added
  (`npm run gen-types`); TanStack Query; Tailwind + shadcn/ui; hosting deferred to Phase 6.
- **Not yet done:** E2E smoke against live backend (requires `docker compose up -d` + backend
  running); `npm run gen-types` to sync types from live `/openapi.json`; streaming (deferred).
- **Next:** run backend + frontend together, take the MVP screenshot, then decide on Phase 2 polish
  (streaming SSE, Vitest component tests) vs moving to Phase 3.

### 2026-06-01 — Phase 1 COMPLETE: RAG MVP shipped (POST /ingest + POST /chat)
- **Branch:** `phase-1-impl` (28 tests, 0 failures). Merge to main when ready.
- **What shipped:** Python 3.12 venv (uv); `LLMClient` seam (Gemini/Ollama/fake); local
  MiniLM-384 embeddings (`sentence-transformers`); content hashing + semantic chunking
  (ADR-0003); hybrid pgvector + full-text retrieval fused with RRF (ADR-0005); cited
  answers (ADR-0006); inline ingest (source→dedupe→chunk→embed→store); chat service
  (retrieve→prompt→generate→persist conversations/messages/retrievals); FastAPI app with
  `/health`, `/ingest`, `/chat` routers + Pydantic v2 schemas (ADR-0007).
- **Off-spec fixes recorded in `implementation-notes.md`:** `tsv` column marked `Computed`
  in ORM (was causing INSERT errors on GENERATED ALWAYS column); chunking overlap falls
  back to word-level when unit-level step-back can't reach the overlap budget; psycopg3
  NULL array params need explicit `bindparam` types (`ARRAY(BigInteger/Text)`);
  `test_defaults` now uses `monkeypatch.delenv` to isolate from CI shell env vars.
- **Verified:** `pytest -v` → 28 passed (16 unit + 12 integration) against live pgvector DB.
- **Next:** Phase 2 — Next.js chat UI (streaming, citations, semantic search). DB-bound
  integration tests (Tasks 2, 9–12) require `SECOND_BRAIN_TEST_DATABASE_URL` set.

### 2026-06-01 — Docker installed; Phase 0 migration applied live (DB on host port 5433)
- **Docker Desktop** installed (Win 11, WSL2 backend, engine v29.5.2); `docker compose up -d`
  brings up `pgvector/pgvector:pg16` (container `second_brain_db`, healthy).
- **Phase 0 migration applied for real** (first time — was offline-only before): `alembic
  upgrade head` → `0001_baseline (head)`. Verified live: 13 relations (12 tables +
  `alembic_version`), `vector` 0.8.2 extension, `ix_embeddings_hnsw` HNSW index.
- **Port moved to 5433:** a native PostgreSQL 16 service owns host 5432, so the Docker DB now
  publishes on **5433** (container 5432). `docker-compose.yml` + `app/config.py` default updated;
  stale `backend/.env` removed. `backend/.env.example` still says 5433 (harness-protected) —
  update to 5433 manually. Detail in `implementation-notes.md`.
- **Next:** Phase 1 implementation per `docs/phase-1-plan.md` — DB-bound tasks (2, 9–12) now unblocked.

### 2026-06-01 — Phase 1 PLAN complete (ADRs 0005–0007, TDD plan, Phase 2 prep)
- **ADRs** → `docs/adr/`: 0005 hybrid retrieval + RRF (pgvector cosine + Postgres full-text,
  RRF `k=60`, `top_k=8`), 0006 prompt + citation contract (`[n]` markers, zero-context refusal,
  no LLM call when no context), 0007 Phase 1 API + execution model (sync SQLAlchemy, inline
  ingest, non-streaming `/chat`, `fake` driver). ADR index updated.
- **Implementation plan** → `docs/phase-1-plan.md`: 13 TDD tasks with real code + tests, a
  DB-free vs DB-bound split, frozen `/ingest` + `/chat` contracts, and run/verify steps.
- **Phase 2 prep** → `docs/phase-2-plan.md`: Next.js chat-UI readiness — contract→TS types,
  the backend deltas Phase 2 needs (`/search`, `/conversations`, `/feedback`, optional SSE),
  and the open decisions for kickoff.
- **Forks decided** (recommended defaults): Python **3.12** venv (machine has 3.12.13),
  **Docker Desktop** test DB, **inline** ingest, **non-streaming** chat. Clarifications: query
  is embedded at chat time; `raw_text` retained until Phase 6. Detail in implementation-notes.
- **No application code yet** — the "approve contracts before scaffolding" gate stands; the plan
  is ready to execute on go.
- **Next:** implement Phase 1 per the plan. Tasks 1, 3–8 need no Docker; tasks 2, 9–12 need
  `docker compose up -d db` + `alembic upgrade head`.

### 2026-06-01 — Phase 0 COMPLETE: data model + migrations + ADRs
- **ER diagram** → `docs/data-model/er-diagram.md` (11 domain tables: sources→documents→chunks→
  embeddings, conversations→messages→retrievals→feedback, tags/document_tags + supporting audit_log,
  jobs). 5 design decisions resolved under the `/goal end of phase 0` directive using the
  recommended defaults.
- **ADRs** → `docs/adr/`: 0001 LLM driver, 0002 embeddings (separate table, `vector(384)`, HNSW),
  0003 chunking (~512 tok / ~15% overlap), 0004 job queue (durable `jobs` + LISTEN/NOTIFY wake-up).
- **Migrations** → `backend/` Alembic scaffold + `0001_baseline.py` (hand-written): `CREATE EXTENSION
  vector`, all tables, GENERATED `tsv` column, GIN(tsv)+GIN(metadata)+HNSW(cosine) indexes, dedupe
  `UNIQUE(source_id, content_hash)`, `set_updated_at()` trigger. ORM models in `app/db/models.py`.
- **Local DB:** `docker-compose.yml` (pgvector/pgvector:pg16). Verify steps in `backend/README.md`.
- **Verification:** models import cleanly (12 tables on metadata) and `alembic upgrade head --sql`
  renders the full DDL offline. **Live `alembic upgrade head` not run here — Docker isn't installed on
  this machine.** Run the 3 commands in backend/README to apply + verify on a box with Docker.
- **Next:** Phase 1 — FastAPI `/ingest` + `/chat`, hybrid retrieval on this schema, `LLMClient`
  (Gemini Flash default, Ollama alt).

### 2026-06-01 — Planning complete
- Finalized the full project plan (`docs/project-plan.md`): architecture, cost-optimized
  stack, Postgres-as-workhorse data layer, JD-coverage matrix, roadmap (phases 0–7),
  Kubernetes learning-track strategy, and capture/research flows.
- Created project home folder, `README.md`, and `MASTER_PROMPT.md`.
- **Next:** Phase 0 — design the Postgres schema and produce the ER diagram.

## Open questions / parking lot
- Which VPS provider to buy (Hetzner ~€4 vs DO/Vultr/Linode ~$5–6). Decide before Phase 6.
- ~~Chunking strategy specifics (size/overlap)~~ — RESOLVED in ADR-0003 (~512 tok / ~15% overlap, semantic boundaries).
- ~~**Install Docker Desktop** before Phase 1 end-to-end / integration tests~~ — DONE 2026-06-01: installed, Phase 0 migration applied live; Docker DB on host **5433** (native PG holds 5432).
- Whether to do the optional managed-cluster (GKE/EKS) capstone in Phase 7.
