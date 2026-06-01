# Progress Log — Second Brain

Running log of what's done, in progress, and next. Keep this current at the end of each
session — the master prompt treats it as the source of truth for "where we are."

## Status at a glance

| Phase | Description | Status |
|---|---|---|
| Planning | Project design, stack, cost model, roadmap | ✅ Complete |
| 0 | Data model + ER diagram + Alembic migrations + pgvector/full-text indexes | ✅ Complete |
| 1 | RAG MVP: FastAPI /ingest + /chat, hybrid retrieval, Gemini via LLMClient | 🟡 Plan complete |
| 2 | Next.js chat UI (streaming, citations, semantic search) | ⬜ Not started |
| 3 | Evaluation + MLOps: eval set, MLflow, A/B, prompt versioning + rollback | ⬜ Not started |
| 4 | MCP server + agentic actions incl. self-research tool | ⬜ Not started |
| 5 | Daily briefing + scheduled pipelines | ⬜ Not started |
| 6 | Productionize on VPS + data-ops hardening | ⬜ Not started |
| 7 | Kubernetes learning track on local k3s/kind | ⬜ Not started |

Legend: ⬜ not started · 🟡 in progress · ✅ complete

## Session log

Add a dated entry per working session. Most recent on top.

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
- **Install Docker Desktop** before Phase 1 end-to-end / integration tests (DB-bound tasks) — not on this machine yet.
- Whether to do the optional managed-cluster (GKE/EKS) capstone in Phase 7.
