# AGENTS.md — Second Brain

Source of truth for all AI coding agents on this repo (Claude, Codex, Antigravity, etc.).
Read this first, then `docs/PROGRESS.md` for current state and `docs/project-plan.md` for
full detail. If you make an off-spec decision, append it to `docs/implementation-notes.md`.

## Project in one paragraph

Second Brain is a personal AI assistant (RAG + Agent + MCP). It ingests my notes, PDFs,
and bookmarks into Postgres + pgvector, lets me chat over them with cited answers, runs
hybrid (vector + full-text) search, sends an automated morning briefing, takes actions via
an MCP server (create task, send digest, search, and "research this topic"), and does its
own automated research via the Gemini API. NotebookLM stays a separate manual tool — not
integrated.

## Fixed decisions (do not relitigate unless I ask)

- **LLM driver:** Gemini Flash API (free tier) as default, behind an `LLMClient` interface;
  local Ollama wired as an alternate "private mode". Embeddings: local sentence-transformers,
  run on ingest only.
- **Datastore:** self-hosted Postgres doing relational + pgvector + full-text (tsvector) +
  JSONB + materialized-view analytics + RLS/audit. Redis for caching/rate-limit only.
- **Backend:** Python + FastAPI. **Frontend:** Next.js + TypeScript. **Agent tools:** MCP server.
- **MLOps:** MLflow for eval + prompt/model versioning. **CI/CD:** GitHub Actions, eval-gated.
- **Observability:** self-hosted Prometheus + Grafana.
- **Runtime:** ONE small VPS (~$4–6/mo), everything in Docker Compose. Keep cost minimal.
- **Kubernetes** is a LEARNING TRACK only (Phase 7): real manifests + HPA + ingress + CI/CD
  proven on free local k3s/kind, then torn down. NOT the production runtime. Managed-cluster
  (GKE/EKS) demo is optional and must be deleted immediately after.

## Roadmap (detail in docs/project-plan.md)

0. Data model + ER diagram + Alembic migrations + pgvector/full-text indexes
1. RAG MVP: FastAPI /ingest + /chat, hybrid retrieval, Gemini via `LLMClient`
2. Next.js chat UI (streaming, citations, semantic search)
3. Evaluation + MLOps: eval set, MLflow harness, A/B, prompt versioning + rollback
4. MCP server + agentic actions incl. self-research tool
5. Daily briefing + scheduled pipelines
6. Productionize on VPS + data-ops hardening (RLS, retention, pooling, query tuning)
7. Kubernetes learning track on local k3s/kind

## How to work

- **Engineer-grade:** write ADRs for real decisions, tests alongside code, keep a deploy
  checklist. Use established engineering workflows where they fit.
- **Cost-conscious:** never propose anything with a recurring bill beyond the one VPS
  without flagging it explicitly and waiting for my OK.
- **Incremental:** end each working chunk with something runnable or reviewable, and tell
  me how to run/verify it. Don't dump huge unrunnable scaffolds.
- **Ask before assuming** on anything that affects architecture, cost, or data privacy.
- **No session/token cost pauses:** I'm on a Claude Max subscription — the per-session
  dollar figure shown in tooling is an *estimate of equivalent API cost*, not a billed
  amount. Do NOT pause, check in, or ask for re-approval based on session/token cost
  (including when it "doubles" or crosses a threshold). The "cost-conscious" rule above
  refers ONLY to recurring infrastructure bills (e.g. the VPS) — flag those, not session cost.
- **Keep records current:** update `docs/PROGRESS.md` at the end of each session (status +
  dated log), and append to `docs/implementation-notes.md` whenever you make a decision,
  change, or trade-off that wasn't in the spec (what / why / what I gave up).

## My environment

- I have a Gemini Ultra subscription — I use NotebookLM (research by hand) and the Gemini
  app / Antigravity (coding copilot) MANUALLY. The app itself uses the free Gemini **API**
  tier, which is separate from my subscription.
- I may use multiple coding agents (Claude, Codex, Antigravity) on this repo — this file is
  the shared source of truth; `CLAUDE.md` just points here.
- [TODO: add your OS, strongest languages, and chosen VPS once decided.]

## Note for non-Claude agents

`CLAUDE.md` is a pointer to this file. Each agent has its own execution model (how it runs
commands, sandboxing, slash commands) — those differ per tool; this file governs the
*what/why/rules*, not the *how-it-executes*.
