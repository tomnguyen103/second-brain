# Progress Log — Second Brain

Running log of what's done, in progress, and next. Keep this current at the end of each
session — the master prompt treats it as the source of truth for "where we are."

## Status at a glance

| Phase | Description | Status |
|---|---|---|
| Planning | Project design, stack, cost model, roadmap | ✅ Complete |
| 0 | Data model + ER diagram + Alembic migrations + pgvector/full-text indexes | 🟡 In progress |
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

### 2026-06-01 — Phase 0 started: data model + ER diagram (awaiting review)
- Drafted the Phase 0 relational schema and ER diagram → `docs/data-model/er-diagram.md`
  (core: sources→documents→chunks→embeddings + conversations→messages→retrievals→feedback +
  tags/document_tags; supporting: audit_log, jobs). Planned index list (HNSW, GIN tsv, dedupe unique).
- Surfaced 5 design decisions needing sign-off (embeddings table/dim, chunking, jobs vs LISTEN/NOTIFY,
  bigint vs uuid keys, raw_text retention) — see "Open design decisions" in the ER doc.
- **Next:** on ER sign-off → write ADR-0002/0003/0004 for the real decisions, then the Alembic
  baseline migration enabling pgvector + tsvector/HNSW/GIN indexes. No migrations written yet (per
  "ER diagram first, review before migrations").

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
