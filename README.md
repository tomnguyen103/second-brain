<div align="center">

# 🧠 Second Brain

**A personal, always-on AI assistant — RAG + Agent + MCP — that runs on one small VPS.**

Ingest your notes, PDFs, and bookmarks; chat over them with **cited** answers; run **hybrid
semantic + full-text search**; get an automated **morning briefing**; take actions through an
**MCP server**; and let it do its own **self-research** — all on the Gemini API free tier for
~$4–6/month.

[![Status](https://img.shields.io/badge/status-Phase%200%20complete-brightgreen)](docs/PROGRESS.md)
[![Stack](https://img.shields.io/badge/stack-FastAPI%20%C2%B7%20Postgres%2Bpgvector%20%C2%B7%20Next.js-blue)](#-tech-stack)
[![Runtime](https://img.shields.io/badge/runtime-Docker%20Compose-2496ED)](docker-compose.yml)
[![Cost](https://img.shields.io/badge/hosting-~%244–6%2Fmo-success)](#-cost-model)

</div>

---

## 📖 Overview

Second Brain is a daily-usable RAG application engineered to demonstrate the full AI-applications
stack end to end: LLM integration, embeddings, vector + full-text retrieval, evaluation/MLOps,
agentic tool-use over MCP, and production data operations on PostgreSQL.

It is deliberately **cost-minimal** — inference runs off-box on the **Gemini Flash free tier**
(with a local Ollama "private mode" behind the same interface), embeddings run locally on ingest,
and everything else is self-hosted in Docker Compose on a single ~$4–6/mo VPS.

> **New here?** Read [`AGENTS.md`](AGENTS.md) (source of truth) → [`docs/PROGRESS.md`](docs/PROGRESS.md)
> (current state) → [`docs/project-plan.md`](docs/project-plan.md) (full detail).

## ✨ Features

| | Feature | What it proves |
|---|---|---|
| 💬 | **Chat over your docs** — RAG with inline source citations | LLM integration · retrieval · summarization |
| 🔎 | **Hybrid search** — pgvector semantic + Postgres full-text, rank-fused | embeddings · vector DB · ranking |
| 📰 | **Morning briefing** — scheduled summary of new inputs | data pipelines · scheduled ops |
| 🛠️ | **Agentic actions via MCP** — create task, send digest, search | tool-use / agentic patterns |
| 🧪 | **Self-research** — "research X" → summarize → store → auto-ingest | agentic pipelines · integration |

## 🧱 Tech Stack

| Layer | Choice |
|---|---|
| **LLM generation** | Gemini Flash API (default) · local Ollama (private mode) — one `LLMClient` interface |
| **Embeddings** | local `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim), on ingest only |
| **Datastore** | self-hosted **PostgreSQL** — relational + **pgvector** + full-text (tsvector) + JSONB + analytics |
| **Cache** | Redis — embedding/query cache, rate limiting |
| **Backend / Frontend** | Python + **FastAPI** · **Next.js + TypeScript** |
| **Agent tooling** | **MCP** server |
| **MLOps / CI-CD** | MLflow (eval + versioning) · GitHub Actions (eval-gated) |
| **Observability** | Prometheus + Grafana |
| **Runtime** | Docker Compose on one VPS · Kubernetes as a Phase 7 learning track (local k3s/kind) |

## 🗺️ Roadmap

| Phase | Description | Status |
|:---:|---|:---:|
| **0** | Data model · ER diagram · Alembic migrations · pgvector/full-text indexes | ✅ Complete |
| 1 | RAG MVP — FastAPI `/ingest` + `/chat`, hybrid retrieval, `LLMClient` | ⬜ Next |
| 2 | Next.js chat UI — streaming, citations, semantic search | ⬜ |
| 3 | Evaluation + MLOps — eval set, MLflow, A/B, prompt versioning + rollback | ⬜ |
| 4 | MCP server + agentic actions (incl. self-research) | ⬜ |
| 5 | Daily briefing + scheduled pipelines | ⬜ |
| 6 | Productionize on VPS + data-ops hardening (RLS, retention, pooling, tuning) | ⬜ |
| 7 | Kubernetes learning track on local k3s/kind | ⬜ |

Live status & dated log: [`docs/PROGRESS.md`](docs/PROGRESS.md).

## 📂 Repository Layout

```
second-brain/
├── README.md                 # you are here
├── AGENTS.md                 # source of truth for all coding agents
├── docker-compose.yml        # local Postgres + pgvector (app services added in Phase 1)
├── backend/                  # FastAPI app + data layer
│   ├── app/db/               # SQLAlchemy models, settings
│   ├── migrations/           # Alembic env + versioned migrations
│   └── README.md             # backend run & verify guide
└── docs/
    ├── project-plan.md       # complete plan + JD-coverage matrix
    ├── PROGRESS.md           # running status log
    ├── implementation-notes.md
    ├── adr/                  # architecture decision records
    └── data-model/
        └── er-diagram.md     # Phase 0 ER diagram
```

## 🚀 Quickstart (Phase 0 — stand up the schema)

Requires Docker and Python 3.11+.

```bash
# 1. Start Postgres + pgvector
docker compose up -d db

# 2. Apply migrations
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows; use bin/activate on macOS/Linux
pip install -r requirements.txt
# .env is optional — config.py defaults to the Docker DB on host port 5433.
# Only copy .env.example if you need overrides, and change :5432 → :5433 first (it still pins 5432).
alembic upgrade head

# 3. Verify (extension, tables, indexes)
docker exec -it second_brain_db psql -U second_brain -d second_brain -c "\dt"
```

Full verification steps (HNSW index, generated tsvector column) are in
[`backend/README.md`](backend/README.md).

## 📐 Architecture & Decisions

- **System design & cost model** → [`docs/project-plan.md`](docs/project-plan.md)
- **Data model (ER diagram)** → [`docs/data-model/er-diagram.md`](docs/data-model/er-diagram.md)
- **Architecture Decision Records** → [`docs/adr/`](docs/adr/)
  - [ADR-0001](docs/adr/0001-llm-driver-local-vs-hosted.md) — hosted Gemini default, local Ollama behind one interface
  - [ADR-0002](docs/adr/0002-embeddings-storage-and-model.md) — embeddings: separate table, `vector(384)`, HNSW
  - [ADR-0003](docs/adr/0003-chunking-strategy.md) — chunking: ~512 tokens, ~15% overlap
  - [ADR-0004](docs/adr/0004-pipeline-trigger-jobs-vs-notify.md) — durable `jobs` table + `LISTEN/NOTIFY`

## 💰 Cost Model

Inference runs on Gemini Flash's free tier (~1,500 req/day — ample for one user), embeddings run
locally on ingest, and Postgres/Redis/MLflow/Prometheus/Grafana are all self-hosted containers on
the same box. The **only recurring cost is the VPS: ~$4–6/month** (e.g. Hetzner CX22, or a
DigitalOcean/Vultr/Linode basic droplet). No GPU, no per-token bill.

---

<div align="center">
<sub>A personal project, used daily — built in public, one phase at a time.</sub>
</div>
