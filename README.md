<div align="center">

# Second Brain

**A personal, always-on AI assistant for streaming cited RAG, hybrid search, daily briefings, and MCP-powered actions.**

Second Brain captures web passages and personal knowledge, stores them in PostgreSQL with pgvector
and full-text indexes, serves citation-validated answers over SSE, produces a morning briefing, and exposes
agentic tools over MCP. The live deployment runs on one VPS behind Caddy HTTPS with single-owner
API-token authentication, a separate admin-token data-ops guard, and documented backup, restore,
rollback, firewall, and secret-rotation operations.

[![Status](https://img.shields.io/badge/status-live-brightgreen)](docs/USAGE.md)
[![Roadmap](https://img.shields.io/badge/roadmap-7%2F7%20complete-success)](docs/PROGRESS.md)
[![Stack](https://img.shields.io/badge/stack-FastAPI%20%7C%20Postgres%2Bpgvector%20%7C%20Next.js-blue)](#tech-stack)
[![TLS](https://img.shields.io/badge/TLS-Caddy%20auto--HTTPS-0F9D58)](deploy/caddy/Caddyfile)
[![CI](https://img.shields.io/badge/CI-unit%20%2B%20integration%20%2B%20eval--gated-blue)](.github/workflows)
[![Runtime](https://img.shields.io/badge/runtime-single%20VPS%20%2B%20Docker%20Compose-success)](#production-architecture)

</div>

---

<div align="center">
  <img src="docs/screenshots/ui-chat-answer.png" alt="Second Brain chat UI with a cited answer" width="820">
  <br>
  <sub>Chat over personal notes with inline source citations.</sub>
</div>

> **Live deployment:** verified on a 2 GB DigitalOcean droplet with Caddy, real Let's Encrypt
> HTTPS via `sslip.io`, hosted Gemini embeddings, and the full 9-service stack running end to end.
> See [docs/USAGE.md](docs/USAGE.md) for live URLs, health checks, backups, rollback, and
> production operations.

## Current Status

Last README synchronization: **2026-06-05**. Live deployment last verified:
**2026-06-02**.

| Area | Status | Notes |
|---|---:|---|
| Product roadmap | Complete | Phases 0-7 are implemented and documented in [docs/PROGRESS.md](docs/PROGRESS.md). |
| Production deployment | Live | Docker Compose on one VPS, fronted by Caddy HTTPS, with localhost-only direct service ports. |
| Production operations | Documented | Bearer-token API access, `ufw` 22/80/443 allow-list, automated DB backup cron, restore drill, health checks, secret rotation, and rollback runbooks. |
| Web UI | Live | Streaming chat, capture, search, ingest, briefing, tasks, research, sources, feedback review, and admin data-ops pages. |
| API | Live | Capture, ingest, streaming and non-streaming chat, search, conversations, feedback analytics, briefing, tasks, research jobs, sources, health, and governed data-ops endpoints. |
| MCP server | Live | `search_notes`, `list_tasks`, and `send_digest` are available by default; `create_task` and `research_topic` require explicit local mutation opt-in. |
| Background jobs | Live | Durable Postgres job queue for daily briefing and async research. |
| CI/CD | Active | Unit tests, integration tests against pgvector, and deterministic eval gate. |
| Kubernetes | Complete as learning track | Manifests, ingress, HPA, monitoring, and CI smoke on local kind; not production runtime. |

## Recent Updates

Most recent first. Full detail lives in [docs/PROGRESS.md](docs/PROGRESS.md) and
[docs/implementation-notes.md](docs/implementation-notes.md).

| Update | Summary | Reference |
|---|---|:---:|
| Frictionless capture | Added `/capture` API and UI for saving a URL, title, notes, tags, and selected text into the normal bookmark ingest path so captures are searchable and citeable. | [usage](docs/USAGE.md) |
| Single-owner authentication | Personal-data routes require `SECOND_BRAIN_API_TOKEN` in production; destructive data-ops also require `SECOND_BRAIN_ADMIN_TOKEN`. Local dev remains keyless unless a token is set. | [usage](docs/USAGE.md) |
| Production operations hardening | Added `ufw` firewall steps, automated backup cron template, restore drill, health checks, secret rotation, and rollback procedures. | [runbooks](docs/runbooks/) |
| Streaming chat | Added SSE `/chat/stream`; the backend now buffers provider chunks until citation and support validation pass, then emits safe deltas plus the same final contract as `/chat`. | [usage](docs/USAGE.md) |
| Local env hygiene | Clarified local Gemini key entry points and tightened `.env` ignore rules while keeping example templates committed. | [progress](docs/PROGRESS.md) |
| App surfaces and Redis paths | Added first-class web pages for operating the app, feedback review workflows, source-backed research, weak-context refusal, and optional Redis-backed rate limits/caches. | [PR #20](https://github.com/tomnguyen103/second-brain/pull/20) |
| Live VPS deployment | Caddy reverse proxy, real HTTPS through `sslip.io`, localhost-only direct service ports, and end-to-end production verification. | [PR #14](https://github.com/tomnguyen103/second-brain/pull/14) |
| Kubernetes learning track | Local kind manifests, ingress, HPA, monitoring, and GitHub Actions smoke workflow were completed and torn down. | [PR #11](https://github.com/tomnguyen103/second-brain/pull/11) |

## Product Capabilities

| Capability | What is implemented |
|---|---|
| Streaming cited RAG chat | `/chat/stream` buffers provider chunks until citation/support validation passes, then sends safe deltas and a persisted completion with `[n]` citation markers. `/chat` remains available as the non-streaming fallback. |
| Web capture | `/capture` saves a URL, title, selected text, notes, and tags as a `bookmark` source/document through the ingest pipeline; it performs no server-side scraping. |
| Hybrid search | pgvector semantic search and PostgreSQL full-text search are fused with reciprocal rank fusion, with configurable weak-context refusal. |
| Source ingestion | `/ingest` accepts text documents, dedupes by content hash, chunks semantically, embeds, tags, and stores them. |
| Morning briefing | A scheduled job summarizes newly ingested documents since the previous briefing and stores the result. |
| MCP tools | A stdio MCP server exposes search, task listing, and digest composition by default; durable task/research mutations are opt-in for trusted local clients. |
| Self-research | `research_topic` can use pasted source text or safe public text/HTML URLs on default HTTP(S) ports, stores provenance, and indexes the resulting `research_note`. |
| Evaluation and MLOps | Fixed eval set, MLflow logging, prompt versioning, A/B configs, rollback by env var, and CI eval gate. |
| Feedback quality review | Feedback analytics and negative-feedback review endpoints turn thumbs into reviewable eval candidates. |
| Redis paths | Optional Redis-backed `/chat` and `/ingest` rate limits, `/search` response caching, and embedding caching are enabled in production; rate limits fail closed by default. |
| Data governance | RLS, audit logging, retention purge, source export, and source erasure endpoints. |
| Single-owner auth | `SECOND_BRAIN_API_TOKEN` protects chat, conversations, capture, ingest, search, briefing, feedback, tasks, research, sources, and admin surfaces; destructive data-ops also require `X-Second-Brain-Admin-Token: <SECOND_BRAIN_ADMIN_TOKEN>`. |
| Observability | Prometheus-format request, cache, and rate-limit metrics at `/metrics`; alert rules and Grafana dashboard configs are retained under `deploy/`, but production Compose does not start monitoring containers until a scanned-clean runtime is selected. |
| Production operations | Docker Compose stack, Caddy HTTPS, bearer-token API access, `ufw` hardening, automated backup cron, restore drill, secret rotation, rollback, and incident response runbooks. |

## User Surfaces

| Surface | Entry point | Notes |
|---|---|---|
| Web app | `/chat`, `/capture`, `/search`, `/ingest`, `/briefing`, `/tasks`, `/research`, `/sources`, `/feedback`, `/admin` | Main daily-use and operations UI. |
| API | `/docs` or `/api/*` in production | Capture, ingest, chat, search, briefing, conversations, feedback analytics, tasks, research jobs, sources, and admin data-ops. Personal-data calls require the API bearer token in production. |
| MCP | `python -m app.mcp_server` | Tool interface for MCP clients such as Claude Desktop. |
| Worker | `python -m app.jobs.worker --loop` | Runs in production; drains briefing and research jobs. |
| Runbooks | [docs/runbooks/](docs/runbooks/) | Deploy, firewall, backup/restore, restore drills, secret rotation, rollback, and incident response procedures. |

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy, Alembic, Pydantic v2 |
| Frontend | Next.js, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query |
| Database | Self-hosted PostgreSQL with pgvector, full-text search, JSONB, RLS, and audit tables |
| Retrieval | Hybrid pgvector cosine search plus PostgreSQL full-text search, fused by RRF |
| LLM generation | `gemini-2.5-flash` by default; local Ollama private mode and fake driver behind the same `LLMClient` interface |
| Embeddings | Local MiniLM or hosted `gemini-embedding-001`, both normalized to 384 dimensions |
| Agent tooling | MCP server over stdio, with durable mutations disabled unless `SECOND_BRAIN_MCP_ENABLE_MUTATIONS=true` |
| Background work | Durable Postgres `jobs` table with `FOR UPDATE SKIP LOCKED`; OS cron enqueues daily briefing |
| Pooling/cache | SQLAlchemy/Postgres connection pooling; Redis powers optional rate limits plus search and embedding caches |
| MLOps | Local MLflow file store, eval harness, prompt registry, A/B configs, CI eval gate |
| Observability | Prometheus metrics endpoint plus retained Prometheus/Grafana config artifacts; monitoring containers are not part of the production Compose runtime |
| Production runtime | Docker Compose on one VPS |
| Kubernetes | Local kind learning track with manifests, ingress, HPA, and CI smoke test |

## Roadmap

| Phase | Description | Status |
|:---:|---|:---:|
| Planning | Project design, stack, cost model, and roadmap | Complete |
| 0 | Data model, ER diagram, Alembic migrations, pgvector/full-text indexes | Complete |
| 1 | RAG MVP with FastAPI `/ingest` and `/chat`, hybrid retrieval, `LLMClient` | Complete |
| 2 | Next.js chat UI with streaming answers, citations, semantic search, conversation history, feedback | Complete |
| 3 | Evaluation and MLOps: eval set, MLflow, A/B configs, prompt versioning, rollback | Complete |
| 4 | MCP server and agentic actions, including self-research | Complete |
| 5 | Daily briefing and scheduled pipelines | Complete |
| 6 | VPS productionization, observability, RLS, retention, pooling, query tuning | Complete |
| 7 | Kubernetes learning track on local kind/k3s | Complete |
| Live | Caddy HTTPS production deployment on a 2 GB droplet | Live |

## Production Architecture

The production system is one Docker Compose project named `second-brain`. The VPS stack is
`db`, `redis`, `api`, `worker`, `frontend`, and public `caddy`. The API exposes `/metrics`
privately on the box, and the Prometheus/Grafana configs remain in `deploy/` for future
self-hosted monitoring, but production Compose no longer ships vulnerable vendor monitoring
containers as an opt-in profile.

```text
Internet HTTPS
    |
    v
+------------------+
| Caddy            |  TLS, Let's Encrypt, sslip.io
| reverse proxy    |  /api/* -> api, /* -> frontend
+---------+--------+
          |
          +-----------------------------+
          |                             |
          v                             v
   +-------------+                +-------------+
   | frontend    |                | api         |
   | Next.js     |                | FastAPI     |
   +-------------+                +------+------+
                                         |
               +-------------------------+------------------+
               |                         |                  |
               v                         v                  v
        +-------------+           +-------------+
        | PostgreSQL  |           | Redis       |
        | pgvector    |           | limits/cache|
        +-------------+           +-------------+
               ^
               |
        +-------------+
        | worker      |
        | jobs        |
        +-------------+

```

## Repository Layout

```text
second-brain/
|-- README.md
|-- AGENTS.md
|-- docker-compose.yml                 # local dev Postgres + pgvector on host port 5433
|-- backend/
|   |-- app/                           # api, chat, retrieval, ingest, llm, embeddings, mcp, jobs, eval
|   |-- migrations/                    # Alembic migrations 0001-0004
|   `-- tests/                         # unit and integration tests
|-- frontend/
|   |-- app/                           # chat, capture, search, ingest, briefing, tasks, research, sources, feedback, admin
|   |-- components/
|   `-- lib/api/
|-- deploy/
|   |-- docker-compose.prod.yml        # base production stack
|   |-- docker-compose.vps.yml.example # Caddy + production binding template
|   |-- caddy/
|   |-- cron/                          # installable VPS cron helper scripts
|   |-- prometheus/
|   |-- grafana/
|   `-- k8s/                           # local Kubernetes learning track
`-- docs/
    |-- USAGE.md                       # live operations guide
    |-- PROGRESS.md                    # authoritative project status log
    |-- project-plan.md
    |-- implementation-notes.md
    |-- adr/
    |-- runbooks/
    |-- data-model/
    `-- screenshots/
```

## Run Locally

Requirements: Docker, Python 3.11+, and Node.js 20+ recommended. The current local frontend
build was verified with Node v24.15.0.

```bash
# 1. Start local Postgres + pgvector.
docker compose up -d db

# 2. Run the backend at http://localhost:8000.
cd backend
python -m venv .venv
# Activate the venv:
#   Windows PowerShell: .\.venv\Scripts\Activate.ps1
#   macOS/Linux:        source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# Use a real Gemini key, or run keyless with the deterministic fake driver.
#   Windows PowerShell: $env:SECOND_BRAIN_LLM_PROVIDER = "fake"
#   macOS/Linux:        export SECOND_BRAIN_LLM_PROVIDER=fake
uvicorn app.main:app --reload

# 3. Run the frontend at http://localhost:3000.
cd ../frontend
npm install
npm run dev
```

Verify the API:

```bash
curl -s http://localhost:8000/health
```

Backend-specific verification is documented in [backend/README.md](backend/README.md).

## Deploy

The production deployment uses the base compose file plus a VPS-specific override. Always pass
the project name explicitly so Compose does not create a second project from the `deploy/`
directory name.

Production secrets live in gitignored `deploy/.env.prod`. Required auth variables:

| Variable | Purpose |
|---|---|
| `SECOND_BRAIN_API_TOKEN` | Required by production Compose; bearer token for normal personal-data routes and the web UI sidebar token field. |
| `SECOND_BRAIN_ADMIN_TOKEN` | Enables export, source deletion, and retention purge when sent as `X-Second-Brain-Admin-Token` alongside the normal API bearer. |

```bash
DC="docker compose -p second-brain -f deploy/docker-compose.prod.yml -f deploy/docker-compose.vps.yml --env-file deploy/.env.prod"
$DC up -d --build
$DC ps
```

The full, verified deployment procedure lives in [docs/USAGE.md](docs/USAGE.md), including:

- `sslip.io` HTTPS with Caddy and Let's Encrypt
- required environment variables
- the `-p second-brain` project-name gotcha
- update procedure
- `ufw` firewall hardening
- automated backup, restore drill, and restore procedure
- secret rotation and rollback
- monitoring tunnels
- admin and data-ops endpoints

## Kubernetes Learning Track

Kubernetes is intentionally **not** the production runtime. The project uses Kubernetes as a
zero-recurring-cost learning track: deploy to local kind/k3s, prove ingress and HPA, capture
evidence, then tear the cluster down.

Key artifacts:

- [deploy/k8s/](deploy/k8s/) - manifests for Postgres, PgBouncer, Redis, API, worker, frontend,
  ingress, HPA, Prometheus, and Grafana
- [deploy/k8s/README.md](deploy/k8s/README.md) - run and teardown guide
- [docs/adr/0014-kubernetes-learning-track.md](docs/adr/0014-kubernetes-learning-track.md) -
  decision record
- [.github/workflows/k8s.yml](.github/workflows/k8s.yml) - CI kind smoke workflow

```bash
kind create cluster --name second-brain --config deploy/k8s/kind-cluster.yaml
kubectl apply -k deploy/k8s
curl -H 'Host: api.second-brain.local' http://localhost/health
kind delete cluster --name second-brain
```

## Architecture and Decisions

- [docs/project-plan.md](docs/project-plan.md) - full system design and roadmap
- [docs/data-model/er-diagram.md](docs/data-model/er-diagram.md) - relational model
- [docs/query-optimization.md](docs/query-optimization.md) - measured Postgres tuning notes
- [docs/USAGE.md](docs/USAGE.md) - live operations guide
- [docs/runbooks/](docs/runbooks/) - deploy, backup/restore, incident response
- [docs/adr/](docs/adr/) - architecture decision records

Selected ADRs:

- [ADR-0001](docs/adr/0001-llm-driver-local-vs-hosted.md) - hosted Gemini default, local Ollama private mode
- [ADR-0002](docs/adr/0002-embeddings-storage-and-model.md) - separate embeddings table, `vector(384)`, HNSW
- [ADR-0005](docs/adr/0005-hybrid-retrieval-rrf.md) - hybrid retrieval with reciprocal rank fusion
- [ADR-0008](docs/adr/0008-evaluation-and-mlflow.md) - evaluation and MLflow
- [ADR-0010](docs/adr/0010-mcp-server-and-agentic-actions.md) - MCP server and agentic actions
- [ADR-0012](docs/adr/0012-productionization-and-data-governance.md) - productionization and governance
- [ADR-0014](docs/adr/0014-kubernetes-learning-track.md) - Kubernetes learning track

## Cost and Privacy Notes

Second Brain is designed to run on one small VPS. The current verified deployment uses a
2 GB DigitalOcean droplet with hosted Gemini embeddings so the box does not need the local
Torch embedding model in memory. Lower-cost VPS providers remain compatible with the same
Compose architecture. Recent operations hardening stays within the same footprint: host
firewall rules, cron backups, restore drills, and rollback procedures add no recurring
infrastructure cost.

Generation uses the configured Gemini API model by default, and embeddings can be either local
MiniLM or hosted Gemini embeddings. When hosted Gemini embeddings are enabled, document text is
sent to Google during ingest as well as during chat generation. For a more private mode, use the
local embedding provider and local Ollama generation path, with the trade-off that the VPS needs
more memory.

## Known Follow-Ups

- Replace single-owner bearer tokens with account/session auth only if the app becomes multi-user.
- Upgrade self-research beyond user-supplied URLs/text into broader external retrieval with
  source-backed citations.
- Promote reviewed feedback candidates into the fixed eval set and dashboard quality trends.
- Keep restore-drill evidence current and periodically copy backups off the VPS to a trusted
  local machine.

---

<div align="center">
<sub>Built as a daily-use personal AI system and a full-stack AI application portfolio project.</sub>
</div>
