# Second Brain — A Personal AI Assistant (RAG + Agent + MCP)

*A daily-usable, shareable AI application engineered to match the AI Applications Developer job description point-for-point.*

---

## The product in one line

An always-on personal AI assistant you talk to every day: it ingests your notes, PDFs, bookmarks, and activity into a vector store, answers questions with **cited** RAG, gives you a **morning briefing**, does **semantic search** across everything you've fed it, and can **take actions** (create tasks, send a digest) through tools exposed over **MCP** — running on the **Gemini API free tier** (with a local-model private mode behind the same interface), hosted on **one small VPS (~$4–6/mo)**, so it's cheap, always-on, and yours.

You are the user. The "tangible value to users" the JD asks for is real on day one because you use it daily.

---

## Why this beats a generic CRUD/dashboard project for the JD

The role is an **AI Applications Developer**. The screening criteria are LLM integration, retrieval/RAG, embeddings + vector DBs, model evaluation, MLOps, and a usable AI-enhanced product. This project is *built around exactly those* rather than bolting AI onto a dashboard. Every required qualification has a concrete home, and the preferred quals (eval, MLOps tooling, vector DBs, React/TS frontend, monitoring) are explicit phases — not afterthoughts.

---

## Tech stack (cost-optimized for 24/7, with résumé-relevant swap points)

| Layer | What you'll run | Cost | JD-named equivalent (call this out in your README) |
|---|---|---|---|
| **LLM generation** | **Gemini Flash API** (free tier) as the default driver; **local Ollama** behind the same interface as fallback/private mode | **$0** (~1,500 req/day free) | OpenAI / Anthropic / Cohere — one `LLMClient` interface, swap by config |
| **Embeddings** | local `sentence-transformers` (run on ingest only) | **$0** | OpenAI `text-embedding-3`, Gemini embeddings |
| **Vector store** | **pgvector** inside self-hosted Postgres | $0 (on the VM) | Pinecone / Weaviate — same retrieval interface |
| **Backend / API** | **Python + FastAPI** | $0 | FastAPI named explicitly in the JD |
| **Frontend** | **React + Next.js + TypeScript** | $0 | named as preferred qual |
| **Agent tooling** | **MCP server** exposing your tools | $0 | MCP + tool-use / agentic patterns |
| **Primary datastore** | **self-hosted Postgres** (relational + pgvector + full-text + JSONB + analytics) on the VM | $0 (on the VM) | PostgreSQL — used to its full depth, not as a blob store |
| **Cache / hot path** | **Redis** for embedding cache, query cache, rate limiting | $0 (on the VM) | named: Redis |
| **Preprocessing** | Pandas/NumPy for chunking, dedupe, PII scrubbing | $0 | named: Pandas, NumPy |
| **MLOps** | **MLflow** for eval runs + prompt/model versioning | $0 (on the VM) | named: MLflow |
| **Compute (24/7)** | **one small VPS**, everything in Docker Compose | **~$4–6/mo** | the always-on host |
| **Containers / orch.** | Docker Compose = the 24/7 runtime; **K8s manifests proven on local k3s/kind** (Phase 7), not run 24/7 | $0 (local cluster torn down after) | named: Docker, Kubernetes |
| **CI/CD** | GitHub Actions (build, test, eval gate, deploy) | $0 (free minutes) | named: GitHub Actions |
| **Observability** | Prometheus + Grafana, self-hosted on the VM | $0 (on the VM) | named: Prometheus, Grafana |

### Cost model — what you actually pay

Essentially everything runs in Docker Compose on **one small VPS**, so your only recurring cost is the box itself: roughly **$4–6/month**. Gemini Flash handles inference off-box on its free tier (~1,500 requests/day — plenty for a personal assistant), so there's **no GPU and no per-token bill**. Embeddings run locally and only on ingest, so they're effectively free. Postgres, Redis, MLflow, Prometheus, and Grafana are all self-hosted containers on the same VM — no managed-service fees, no external storage limits.

**VPS options (x86, no ARM-capacity lottery, predictable):** Hetzner CX22 (~€4/mo, 2 vCPU / 4 GB), DigitalOcean / Vultr / Linode basic (~$5–6/mo). A 4 GB box comfortably runs the whole stack. **The $0 alternative:** Oracle Cloud Always Free (up to 4 ARM cores / 24 GB RAM, never expires) — far more powerful, but ARM capacity is often hard to provision and idle instances can be reclaimed, so it's the "free but fiddly" path.

**Why Gemini Flash API instead of local-only LLM:** keeping a capable model resident 24/7 needs real RAM/CPU (or a GPU) and burns power on a box you're paying for; offloading generation to Gemini's free tier keeps the VPS tiny and cheap. **The privacy trade-off** (note this in your README for the GDPR story): query text and retrieved chunks transit to Google. The plan keeps a **local Ollama path behind the same `LLMClient` interface**, so you can flip to a fully-private, no-external-calls mode — and demonstrating that abstraction is itself a strong engineering signal.

### Using your Gemini Ultra subscription (by hand, not via the app's API)

Your Ultra subscription and the Gemini *API* are billed separately — Ultra powers the consumer apps, not a high-quota API key — so the app calls the free **Gemini API** tier, while you get Ultra's value manually:

- **NotebookLM** — feed it this plan and your design docs; use Q&A and audio overviews to study and pressure-test the architecture. (No free programmatic API, so it stays a hand tool, not an app integration.)
- **Gemini app / Antigravity** — your dev copilot while building (code gen, debugging, iteration) at Ultra's higher limits.

---

## Architecture

```
            ┌─────────────────────────────────────────────────────────┐
            │  Next.js + TypeScript  Chat / Search / Briefing UI       │
            │  (the daily-usable, screenshot-able surface)             │
            └───────────────┬─────────────────────────────────────────┘
                            │ REST / streaming
                            ▼
            ┌─────────────────────────────────────────────────────────┐
            │  FastAPI Backend                                         │
            │  • /chat (RAG)   • /search   • /briefing   • /ingest     │
            │  • orchestration: retrieve → rank → prompt → generate    │
            └───┬───────────────┬───────────────────────┬─────────────┘
                │               │                       │
        ┌───────▼──────┐ ┌──────▼───────┐       ┌────────▼─────────┐
        │ Embedding /  │ │  LLMClient   │       │  MCP Server      │
        │ ingest worker│ │  Gemini Flash│       │  tools: create   │
        │ (local model │ │  (default) / │       │  task · digest · │
        │  on ingest)  │ │  Ollama (alt)│       │  search ·        │
        └───────┬──────┘ └──────────────┘       │  RESEARCH topic  │
                │                               └────────┬─────────┘
                ▼                                        │ actions
        ┌──────────────────────────────┐                ▼
        │ Postgres (workhorse)         │        (Asana/GitHub/email
        │ relational core · pgvector   │         via existing connectors)
        │ tsvector full-text · JSONB   │
        │ mat. views · RLS · audit     │
        │ LISTEN/NOTIFY job triggers   │
        └──────────────────────────────┘
                ▲   ▲
        Redis ──┘   │ scheduled
       (cache)      │
        ┌───────────┴────┐
        │ Briefing job    │  pulls new inputs → summarizes → stores digest
        └────────────────┘

  All of the above run as containers in ONE Docker Compose stack on a single ~$4–6/mo VPS.
  Cross-cutting: Alembic migrations · MLflow (eval + versioning) · Prometheus/Grafana · GitHub Actions CI/CD
```

---

## The five daily-use features (and the JD bullet each proves)

**1. Chat over my docs (RAG with citations).** Ask a question; the system embeds it, retrieves the top-k relevant chunks from pgvector, builds a prompt, and the LLM answers with sources cited. *Proves: LLM integration, embeddings, vector DB, retrieval-based architecture, summarization.*

**2. Daily briefing.** A scheduled job pulls new inputs (notes added, GitHub activity, RSS), summarizes them, and stores a morning digest you open with coffee. *Proves: data pipelines, preprocessing, summarization, scheduled/production operation.*

**3. Smart semantic search.** Type a vague query, get the most relevant items ranked by vector similarity + reranking. *Proves: retrieval, ranking, evaluation metrics.*

**4. Agentic actions via MCP.** The assistant can call tools — "add this to my tasks," "email me the digest" — exposed through an **MCP server** you build. *Proves: tool-use/agentic patterns, integration, and satisfies your learn-MCP goal.*

**5. Self-research ("research this topic").** When a topic interests you, you tell the assistant to research it; a **research tool** (Gemini + optional web search) gathers and summarizes the topic, then writes the result back as a new source — which the ingestion pipeline auto-embeds, so it's permanently searchable in your brain. One command in → a cited, stored research note out. *Proves: agentic tool-use, summarization, pipeline integration.*

### Capture & research flows — manual vs automated

The Second Brain does its **own** automated research; **NotebookLM stays a separate, by-hand studio** (no app integration, since it has no free programmatic API — avoiding brittle unofficial wrappers is a deliberate choice).

- **Automated path (in the app):** you issue "research X" → the agent's research tool calls Gemini (+ optional web search) → summarizes → stores it as a source → the pipeline embeds it → it's searchable. The only manual act is asking.
- **Manual path (outside the app):** when you want deep study, you use NotebookLM by hand (feed it sources, get summaries/audio overviews). If something there is worth keeping, you paste it into the app to ingest — a deliberate human step, not an automated bridge.

Why no Gemini-chat → NotebookLM → brain auto-pipe: Gemini chats emit no events to hook, and NotebookLM has no free API — so a programmatic chain would be fragile. The app owning its research tool is the robust, controllable equivalent.

---

## Data layer — Postgres as the workhorse (design narrative)

The earlier draft under-used the database. This version makes Postgres a first-class, demonstrable component: one engine carrying relational modeling, vector search, full-text search, flexible metadata, analytics, and governance. Redis stays in the picture for what it's actually good at (caching, rate limiting), so the architecture still reads like realistic microservices rather than "everything in one box." The point you can show a reviewer: *I didn't just store vectors in Postgres — I used relational design, hybrid retrieval, migrations, indexing, and SQL analytics.*

**Relational core (real modeling, not a blob).** A normalized schema with proper foreign keys and constraints: `sources` (where data came from — a notes folder, GitHub, RSS), `documents` (one ingested item, belongs to a source), `chunks` (the retrievable units, belong to a document), `embeddings` (vector per chunk), `tags` and a `document_tags` join, `conversations` and `messages` (your chat history), `retrievals` (which chunks were returned for which query — the link between a question and its evidence), and `feedback` (thumbs up/down on answers). This relational spine is what lets you answer questions like "which sources do my best answers come from" in SQL — and it's exactly the modeling depth a PostgreSQL-focused reviewer looks for.

**Vector search via pgvector.** Embeddings live in a `vector` column with an HNSW (or IVFFlat) index for fast approximate nearest-neighbor search. You'll tune index parameters and measure recall vs latency — a concrete query-optimization story.

**Full-text search via tsvector + GIN — and hybrid retrieval.** Chunks also carry a `tsvector` column with a GIN index for keyword search. Retrieval then **fuses** semantic (pgvector) and lexical (full-text) results — e.g. reciprocal-rank fusion — which typically beats either alone. This hybrid-in-one-database approach is a genuine strength most pure-vector projects skip, and it's a great thing to write up and screenshot.

**JSONB for flexible metadata.** Each source shapes its data differently (a GitHub event vs a PDF vs a bookmark). A `metadata JSONB` column with a GIN index keeps the schema clean while staying queryable — demonstrating you know when to normalize and when not to.

**Analytics in SQL.** Materialized views and window functions power the usage dashboard and the eval analytics: answer latency percentiles, retrieval hit rates, feedback trends over time, most-cited sources. CTEs and window functions here show SQL fluency beyond CRUD. Refresh strategy (scheduled `REFRESH MATERIALIZED VIEW CONCURRENTLY`) is itself a small ops decision worth an ADR.

**Pipeline triggers without extra infra.** Postgres `LISTEN/NOTIFY` (or a simple `jobs` table polled by workers) drives ingest and briefing without standing up a separate broker — a deliberate "use the database you already have" choice you can defend in an ADR (and contrast with the Redis/queue alternative).

**Privacy & governance (the GDPR/CCPA story).** Row-level security scopes data access; an `audit_log` table records access/changes; a retention policy (TTL on raw inputs after embedding) and a documented "delete my data" path satisfy the JD's data-governance and anonymization bullets. PII scrubbing happens in preprocessing before storage; the audit + retention tables prove you thought about the lifecycle.

**Migrations & operability.** Alembic-versioned migrations (every schema change reviewed and reversible), backward-compatible migration discipline tied into the deploy checklist, connection pooling (PgBouncer) for the always-on service, and a backup/restore runbook. These turn "I use Postgres" into "I operate Postgres."

**Redis, kept honest.** Redis caches embeddings (don't re-embed identical text), caches hot query results, and enforces rate limits — the things a cache/in-memory store is genuinely better at than Postgres. Keeping both, each for its strength, is the realistic-architecture signal.

---

## JD coverage matrix

| JD requirement | Where this project covers it |
|---|---|
| Design/implement AI features (chatbot, search, summarization, recommendations) | Features 1–4: chat, search, briefing, agent |
| Robust backend APIs, low latency/high throughput | FastAPI service; latency tracked as an eval metric; Redis caching for embeddings |
| Integrate AI with frontend; UI/UX collaboration | Next.js/TS chat UI with streaming responses |
| Data pipelines, preprocessing, quality/privacy/security | Ingest worker: chunking, dedupe, PII scrubbing; Postgres constraints enforce quality; local models = privacy |
| **PostgreSQL** (named) — modeling, queries, optimization | Normalized relational schema; hybrid pgvector + full-text search; JSONB; materialized views/window functions; HNSW/GIN index tuning with `EXPLAIN ANALYZE` |
| Feature stores / structured + unstructured data | Chunks + embeddings + JSONB metadata; relational core ties unstructured text to structured sources/tags |
| Data governance, retention, anonymization (GDPR/CCPA) | Row-level security, `audit_log`, retention TTL, documented delete-my-data path, PII scrubbing before storage |
| Schema versioning / migrations | Alembic versioned, reversible migrations tied to the deploy checklist |
| Evaluate models — performance, fairness, bias, latency, reliability | Eval harness in MLflow: answer quality, latency, refusal/bias checks |
| A/B testing + rollback strategies | A/B two prompt/model configs; rollback via versioned prompts + feature flag |
| MLOps: versioning, CI/CD for ML, containerization, orchestration | MLflow versioning; GitHub Actions eval-gated deploy; Docker Compose runtime; **K8s manifests + HPA + ingress proven on local k3s/kind** (Phase 7) |
| Monitoring: logging, metrics, tracing, alerting, incident response | Prometheus/Grafana dashboards; alerts on latency/error/queue; runbooks |
| Clean code, API docs, architecture diagrams, dev guides | OpenAPI docs, this architecture doc, per-service READMEs |
| Cross-functional translation of requirements | ADRs + system-design docs (you play PM/DS/Sec) |
| Privacy, security, ethical AI, bias mitigation, explainability | PII scrubbing, GDPR notes, citations = explainability, bias eval |
| Code reviews, unit/integration tests | Self-review checklist; pytest unit + integration against real Postgres |
| **Python proficiency / FastAPI** | Backend core |
| **LLM integration (OpenAI/Cohere/Anthropic)** | Abstracted LLM client; swap from Ollama with a config flag |
| **Embeddings, vector DBs (Pinecone/Weaviate), retrieval** | pgvector now; documented Pinecone/Weaviate swap |
| **Cloud + DevOps (Docker, CI/CD, K8s)** | Docker Compose runtime; GitHub Actions; K8s track on local k3s/kind (Phase 7); VPS deploy |
| **React/TypeScript frontend** (preferred) | Next.js dashboard |
| **MLflow / monitoring (Prometheus/Grafana)** (preferred) | Explicit phases |
| **GDPR/CCPA, anonymization** (preferred) | PII pipeline + privacy README section |

If you can point at every row of this table in a repo, you are a credible candidate for this role.

---

## Phased roadmap — each phase ends with something shareable

**Phase 0 — Data model first.** Design the relational schema (sources, documents, chunks, embeddings, tags, conversations, messages, retrievals, feedback), set up Alembic migrations, enable pgvector + full-text columns and their indexes. **Shareable:** a clean ER diagram — a strong "I lead with data modeling" signal.

**Phase 1 — RAG MVP (the first screenshot).** FastAPI `/ingest` + `/chat` on the Phase 0 schema, hybrid retrieval (pgvector + full-text fusion), Gemini Flash via the `LLMClient` interface (Ollama wired as the alternate). Drop in a folder of your notes/PDFs, ask a question, get a cited answer. **Shareable:** "Built a RAG assistant over my own notes with hybrid Postgres search — here's it answering with sources." 

**Phase 2 — The daily-usable UI.** Next.js/TS chat interface with streaming, source citations, and semantic search. This is your primary LinkedIn/Instagram screenshot. **Shareable:** a clean chat UI demo.

**Phase 3 — Evaluation + MLOps.** Build an eval set (questions + expected sources), an eval harness logging answer quality/latency/refusal to **MLflow**, A/B two configs, and prompt versioning with rollback. **Shareable:** an MLflow dashboard comparing two model/prompt versions — a *strong* differentiator post.

**Phase 4 — MCP server + agentic actions (incl. self-research).** Expose tools via an MCP server — create task, send digest, search, and **research-this-topic** (Gemini + optional web search → summarize → store as a source the pipeline auto-ingests). The assistant calls them. **Shareable:** "Taught my assistant to research a topic and file it into my brain through MCP." (You learn MCP here.)

**Phase 5 — Daily briefing + pipelines.** Scheduled summarization job; morning digest. **Shareable:** your actual morning briefing.

**Phase 6 — Productionize + data ops.** Deploy the Docker Compose stack to the VPS; GitHub Actions CI/CD with an **eval gate** (deploy blocked if quality regresses); self-hosted Prometheus/Grafana, alerting, runbooks. Data-layer hardening: RLS + audit log, retention TTL and delete-my-data path, PgBouncer pooling, backup/restore runbook, and a query-optimization pass (`EXPLAIN ANALYZE`, index tuning) with before/after numbers. **Shareable:** a Grafana dashboard + ER diagram + a query-tuning before/after — the "I can model *and* operate this" proof.

**Phase 7 — Kubernetes track (learn it without paying to run it).** *Compose remains the 24/7 runtime — this phase is for K8s competence and the JD bullet, run on a free, ephemeral local cluster and torn down after.* See the dedicated **Kubernetes strategy** section below for the full breakdown. In short: author real manifests, prove them on local **k3s/kind**, demonstrate autoscaling and ingress, and wire CI/CD to the cluster. **Shareable:** a screenshot of your pods scaling under load (`kubectl get hpa`/`get pods`) and your Actions pipeline deploying to the cluster — plus a README note explaining *why* the live system runs on Compose. **Optional capstone (only if you want the shiniest demo):** a short, deliberate run on a managed cluster (GKE/EKS), captured, then deleted — see cost note below.

---

## Kubernetes strategy — learn it, demonstrate it, don't pay to run it 24/7

**The decision, stated plainly:** the live assistant runs on **Docker Compose** on one small VPS. Kubernetes is deliberately *not* the production runtime, because this is a single-user app — K8s's value (multi-node scheduling, autoscaling under real traffic, self-healing across machines, team rolling-deploys) solves problems you don't have here, and running it 24/7 would mean either a $70+/mo managed cluster or the operational overhead of babysitting a single-node cluster for zero benefit. **Being able to explain that trade-off is a stronger interview signal than "I run everything on K8s"** — it shows you know the tool *and* when not to reach for it.

**The key insight:** learning K8s does not require K8s *uptime*. Every skill below is practiced on a **free local cluster (k3s or kind)** you spin up, deploy to, screenshot, and tear down — $0, and zero risk to your running app.

| K8s skill (you wanted all four) | What you build/demonstrate on local k3s/kind | Why it's real, not cosmetic |
|---|---|---|
| **Core workloads** | Deployments, Services, ConfigMaps/Secrets, a namespace for the app | The everyday objects; identical whether the cluster lives 5 min or 5 months |
| **Health + scaling** | Liveness/readiness probes, resource requests/limits, a **HorizontalPodAutoscaler** — then generate load and watch pods scale | You *cannot* show autoscaling on Compose, so this is genuinely K8s-specific learning |
| **Ingress + config** | An ingress controller routing to your services + TLS; templated with **Helm or Kustomize** (dev/prod overlays) | Demonstrates routing and environment config the way real clusters do |
| **CI/CD to K8s** | GitHub Actions builds images and `kubectl apply`s to the cluster, eval-gated | The *pipeline* is the artifact and doesn't need a permanent cluster |

**Cost guardrail (important to you):** the entire Phase 7 baseline is **$0** — k3s/kind run on your own machine or even on the same VPS temporarily. **Do not** stand up a managed cluster as a permanent thing. The *only* optional spend is the capstone: deploy to GKE/EKS for a single afternoon to capture a real-cloud rolling-deploy screenshot, then **delete the cluster immediately** (set a calendar reminder; clusters left running are the classic surprise bill). Even that is a few dollars at most — and it's entirely skippable, since the local-cluster proof already backs the JD bullet.

---

## Engineering-workflow practice (your original goal, preserved)

Every workflow from your toolkit still applies, now on an AI system: **ADRs** (local vs hosted models, pgvector vs Pinecone, chunking strategy), **system design** (retrieval pipeline, service boundaries), **testing strategy** (unit + integration + an *eval* suite unique to ML), **deploy checklist** (eval-gated rollout), **incident response** (model serving down, bad retrieval, hallucination spike), **runbooks**, **monitoring**, **tech-debt audit**, **standup** (auto-generated from your activity), **documentation**. The AI-specific additions — eval, A/B, rollback, MLOps — are exactly the bullets the JD weights most.

---

## What to share, and where

- **LinkedIn:** Phase 2 chat UI, Phase 3 MLflow A/B comparison, Phase 6 architecture diagram + Grafana, Phase 7 K8s autoscaling screenshot (with the "why Compose runs production" note — recruiters love the judgment). Pair each with a short "what I learned" line (RAG, eval, MLOps, MCP, K8s).
- **Instagram/Facebook:** the polished chat UI and the morning-briefing screenshot — visual, relatable ("my AI reads my notes for me").
- **Job boards / résumé:** link the repo; lead with the JD-coverage matrix as the README's headline so a recruiter sees the match instantly.

---

## First moves when you're ready

1. **Data model + ER diagram** (Phase 0) — the relational schema, indexes, and migration setup. Leading with this is the strongest Postgres signal.
2. **ADR #1 — Local vs hosted models** (and the abstraction that lets you swap). Plus a short ADR on hybrid retrieval (pgvector + full-text) and LISTEN/NOTIFY vs Redis queue.
3. **System-design doc** — lock the ingest→retrieve→generate pipeline.
4. **Scaffold Phase 1** — FastAPI `/ingest` + `/chat`, hybrid search on the Phase 0 schema, `LLMClient` interface with Gemini Flash as default and Ollama as the alternate.

Tell me which to start and I'll produce it. I'd suggest the **data model + ER diagram first** (it now anchors the whole project and is itself a résumé artifact), then the ADRs, then scaffold the RAG MVP.
