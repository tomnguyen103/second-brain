# Progress Log — Second Brain

Running log of what's done, in progress, and next. Keep this current at the end of each
session — the master prompt treats it as the source of truth for "where we are."

## Status at a glance

| Phase | Description | Status |
|---|---|---|
| Planning | Project design, stack, cost model, roadmap | ✅ Complete |
| 0 | Data model + ER diagram + Alembic migrations + pgvector/full-text indexes | ✅ Complete |
| 1 | RAG MVP: FastAPI /ingest + /chat, hybrid retrieval, Gemini via LLMClient | ⬜ Not started |
| 2 | Next.js chat UI (streaming, citations, semantic search) | ⬜ Not started |
| 3 | Evaluation + MLOps: eval set, MLflow, A/B, prompt versioning + rollback | ⬜ Not started |
| 4 | MCP server + agentic actions incl. self-research tool | ⬜ Not started |
| 5 | Daily briefing + scheduled pipelines | ⬜ Not started |
| 6 | Productionize on VPS + data-ops hardening | ⬜ Not started |
| 7 | Kubernetes learning track on local k3s/kind | ⬜ Not started |

Legend: ⬜ not started · 🟡 in progress · ✅ complete

## Session log

Add a dated entry per working session. Most recent on top.

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
- Chunking strategy specifics (size/overlap) — settle with an ADR in Phase 0/1.
- Whether to do the optional managed-cluster (GKE/EKS) capstone in Phase 7.
