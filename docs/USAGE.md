# Second Brain — Usage Guide

How to use and operate the live deployment. Last verified **2026-06-02** against the
production droplet. Web UI/API surface last updated **2026-06-04**.

---

## Live URLs

> Replace `YOUR_VPS_IP` in the URLs below with your droplet's public IP address.

| What | URL | Notes |
|---|---|---|
| **Web UI** | **https://YOUR_VPS_IP.sslip.io** | Chat, search, ingest, briefing, feedback, tasks, research, sources, admin. Redirects to `/chat`. |
| **API (app path)** | https://YOUR_VPS_IP.sslip.io/api | Behind Caddy, same TLS cert. e.g. `/api/health`, `/api/chat`. |
| **API (direct)** | http://localhost:8000 *(on the box or via SSH tunnel)* | Plain HTTP, bound to localhost only. Handy for quick `curl`. |
| **Swagger UI** | http://localhost:8000/docs *(on the box or via SSH tunnel)* | Interactive "try it" docs for every endpoint. |
| Grafana | http://localhost:3001 *(via SSH tunnel)* | admin / `GRAFANA_ADMIN_PASSWORD`. Not public. |
| Prometheus | http://localhost:9090 *(via SSH tunnel)* | Not public. |

> **TLS:** `YOUR_VPS_IP.sslip.io` is a wildcard-DNS hostname that resolves to the droplet's
> IP (`sslip.io` maps `<ip>.sslip.io → <ip>`), which lets Caddy obtain a real, auto-renewing
> Let's Encrypt certificate **without owning a domain**. `http://` auto-redirects to `https://`.
> To switch to a real domain later: point an A record at the IP, set `CADDY_SITE_ADDRESS` in
> `deploy/.env.prod` and the frontend build arg in `deploy/docker-compose.vps.yml`, then rebuild
> the frontend + restart Caddy.

---

## What it is

Second Brain is a personal RAG assistant: you **ingest** notes/text, it embeds and stores them
in Postgres + pgvector, and you **chat** or **search** over them with **cited** answers. It also
produces a **daily briefing** and exposes **agentic tools** over MCP. The LLM
(`gemini-2.5-flash`) and embeddings (`gemini-embedding-001`) are hosted Gemini API calls, so the
box needs no GPU and fits in 2 GB RAM.

**Architecture:** one Docker Compose project (`second-brain`) on one DigitalOcean droplet, 9
services: `caddy` (HTTPS reverse proxy) → `frontend` (Next.js) + `api` (FastAPI); `worker`
(daily briefing + async research); `db` (pgvector), `pgbouncer`, `redis`; `prometheus` +
`grafana`.

---

## Using the Web UI

Open **https://YOUR_VPS_IP.sslip.io**. You get:

- **/chat** — ask a question; the answer comes back with inline `[1]`,`[2]` citation markers.
  Click a marker to see the source card (title, snippet, score). A conversation sidebar lists
  past threads (auto-refresh). Thumbs up/down records feedback. A "private mode" toggle routes
  that turn through the local LLM path instead of Gemini (if configured).
- **/search** — raw hybrid (vector + full-text) search results with source/tag filters, no LLM.

The browser talks to the API at `…/api` through Caddy (same origin, so no CORS issues).

Additional web pages:
- **/ingest** - add manual notes or text documents, with source metadata and tags.
- **/briefing** - read the latest stored briefing and recent briefing history.
- **/feedback** - review thumbs feedback trends, negative examples, cited source context, and
  staged eval candidates.
- **/tasks** - create tasks and mark them open, done, or cancelled.
- **/research** - enqueue async research jobs with optional public source URLs or pasted source
  text, then watch queued/running/done/failed status.
- **/sources** - inspect sources, documents, chunk counts, tags, and retention state.
- **/admin** - run token-guarded export, source delete, and retention purge actions.

---

## Using the API

Base URL `https://YOUR_VPS_IP.sslip.io/api`. Examples use `curl` (works on Windows 11 and
the box).

### Add notes — `POST /ingest`
`source.type` must be one of: **`manual`**, `notes_folder`, `github`, `rss`, `pdf_upload`,
`bookmark`, `research_note`. Use `manual` for ad-hoc text.

```bash
curl -X POST https://YOUR_VPS_IP.sslip.io/api/ingest \
  -H "Content-Type: application/json" -d '{
    "source": {"type": "manual", "name": "My Notes"},
    "documents": [
      {"title": "HNSW tuning", "content": "m=16, ef_construction=64, cosine distance.",
       "tags": ["postgres", "vector"]}
    ]
  }'
```
Re-ingesting identical content is deduped by content hash (`status: "duplicate"`).

### Ask — `POST /chat`
```bash
curl -X POST https://YOUR_VPS_IP.sslip.io/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How should I tune the HNSW index?"}'
```
Returns `answer` (with `[n]` markers), `citations[]`, token `usage`, `model`, `latency_ms`, and
`conversation_id`. Pass `conversation_id` back to continue a thread. Options:
`{"message":"…","top_k":8,"filters":{"tags":["postgres"]},"options":{"private_mode":false}}`.
If nothing relevant is found it refuses rather than inventing an answer.

### Search — `GET /search`
```bash
curl "https://YOUR_VPS_IP.sslip.io/api/search?q=hnsw+tuning&top_k=5"
```

### Redis-backed safeguards and caches
Production Compose enables Redis for three conservative hot paths:

- `POST /chat` and `POST /ingest` use fixed-window API rate limits keyed by client IP.
- `GET /search` can cache hot search responses briefly; successful ingest bumps a cache epoch so
  newly embedded content is not hidden behind an old result.
- Query/content embeddings can be reused from Redis by hashed text keys. Raw note/query text is not
  stored in Redis keys; values are transient vectors under Redis' in-memory LRU policy.

Local development defaults Redis off (`SECOND_BRAIN_REDIS_ENABLED=false`). To test it locally,
start a Redis instance and set:

```bash
SECOND_BRAIN_REDIS_ENABLED=true
SECOND_BRAIN_REDIS_URL=redis://localhost:6379/0
```

Useful knobs:

| Env var | Default |
|---|---:|
| `SECOND_BRAIN_RATE_LIMIT_ENABLED` | `true` |
| `SECOND_BRAIN_CHAT_RATE_LIMIT_REQUESTS` | `30` per `60s` |
| `SECOND_BRAIN_INGEST_RATE_LIMIT_REQUESTS` | `10` per `60s` |
| `SECOND_BRAIN_SEARCH_CACHE_ENABLED` | `true` |
| `SECOND_BRAIN_SEARCH_CACHE_TTL_SECONDS` | `120` |
| `SECOND_BRAIN_EMBEDDING_CACHE_ENABLED` | `true` |
| `SECOND_BRAIN_EMBEDDING_CACHE_TTL_SECONDS` | `604800` |

Redis failures fail open: the app logs cache/rate-limit errors and continues through Postgres/LLM
rather than making Redis a hard dependency. Prometheus exposes `cache_events_total` and
`rate_limit_events_total` alongside request metrics.

### Other endpoints
- `GET /briefing`, `GET /briefing/history` — daily briefings (see below).
- `GET /conversations`, `GET /conversations/{id}` — chat history with reconstructed citations.
- `POST /feedback` — `{"message_id": 123, "rating": 1}` (rating is `1` or `-1`).
- `GET /health` — `{"status":"ok","db":"ok","embedder":"…"}`.

Feedback quality endpoints:
- `GET /feedback/analytics?days=30` - feedback totals, daily trend buckets, model stats, and
  top cited documents on negative feedback.
- `GET /feedback/negative` - negative feedback review queue with conversation, message, question,
  answer, retrieval, and citation context.
- `GET /feedback/eval-candidates` - negative feedback exported as review-first eval candidate
  cases. `expected_docs` is inferred from cited documents; edit labels before adding cases to the
  fixed eval set.

Additional API endpoints:
- `GET /sources`, `GET /sources/{id}/documents` - source and document overview.
- `GET /tasks`, `POST /tasks`, `PATCH /tasks/{id}` - task list and status updates.
- `POST /research/jobs`, `GET /research/jobs`, `GET /research/jobs/{id}` - queued source-backed
  research jobs.

### Feedback analytics and eval candidates
Use feedback analytics to turn thumbs into reviewable quality data:

```bash
curl "https://YOUR_VPS_IP.sslip.io/api/feedback/analytics?days=30"
curl "https://YOUR_VPS_IP.sslip.io/api/feedback/negative?limit=25&days=30"
curl "https://YOUR_VPS_IP.sslip.io/api/feedback/eval-candidates?limit=25&days=30"
```

Eval candidate responses mirror the fixed eval dataset shape:

```json
{
  "cases": [
    {
      "id": "feedback-123",
      "question": "What did I ask?",
      "expected_docs": ["Cited document title"],
      "expected_keywords": [],
      "expect_refusal": false,
      "metadata": {
        "feedback_id": 123,
        "needs_review": true
      }
    }
  ]
}
```

### Source-backed research - `POST /research/jobs`
Research does not use a paid search API. Provide your own evidence as public URLs or source text;
the worker fetches/parses safe public text/HTML URLs, asks the configured LLM to ground the note
in those excerpts, stores a `research_note`, and writes provenance into the stored document
metadata.

```bash
curl -X POST https://YOUR_VPS_IP.sslip.io/api/research/jobs \
  -H "Content-Type: application/json" -d '{
    "topic": "reciprocal rank fusion",
    "source_urls": ["https://example.com/rrf-notes"],
    "source_texts": [
      {
        "title": "Manual excerpt",
        "uri": "manual://rrf",
        "text": "Reciprocal rank fusion combines independently ranked result lists."
      }
    ]
  }'
```

When the worker finishes, `GET /research/jobs/{id}` returns `result.evidence_count` and
`result.sources[]` with source IDs (`S1`, `S2`), title/URI, status, and excerpts. The stored
research document has the same `sources[]`, `source_count`, and `grounding` fields in
`documents.metadata`.

---

## Daily briefing

The `worker` service drains a job queue continuously; a host cron enqueues one `briefing` job a
day. It's already installed at **`/etc/cron.d/second-brain-briefing`** (07:00 server time). Read
it the next morning at `GET /api/briefing`. Each run summarizes documents ingested since the
previous briefing. Enqueue one on demand:

```bash
cd /root/second-brain
docker compose -p second-brain \
  -f deploy/docker-compose.prod.yml -f deploy/docker-compose.vps.yml \
  --env-file deploy/.env.prod exec -T worker python -m app.jobs.enqueue briefing
```

---

## Agentic tools (MCP)

The MCP server (`backend/app/mcp_server.py`, stdio) exposes five tools: `search_notes`,
`create_task`, `list_tasks`, `send_digest`, and `research_topic`. `research_topic(topic,
source_urls?, source_texts?)` accepts optional public URLs or pasted snippets, stores the grounded
note as a `research_note`, auto-indexes it, and returns `evidence_count` plus `sources[]`
provenance. Wire it into a local MCP client (e.g. Claude Desktop) - run it on the box or locally
with the DB DSN + Gemini key in its `env`. Set `SECOND_BRAIN_LLM_PROVIDER=fake` for a keyless
smoke test.

---

## Operating the box

```bash
ssh root@YOUR_VPS_IP
cd /root/second-brain

# the stack is ONE project; always pass -p second-brain + BOTH compose files + the env file:
DC="docker compose -p second-brain -f deploy/docker-compose.prod.yml -f deploy/docker-compose.vps.yml --env-file deploy/.env.prod"

$DC ps                       # status of all 9 services
$DC logs -f api worker       # follow logs
$DC restart api              # restart one service
$DC up -d                    # reconcile / start everything
$DC down                     # stop the whole stack
```

> **Gotcha:** the project name is **`second-brain`** and the stack is composed of **two** files.
> Running `docker compose -f deploy/docker-compose.prod.yml …` *without* `-p second-brain` (and
> without the `vps.yml` override) resolves to a **different project** (`deploy`) and will spin up
> an empty duplicate. Always use the `$DC` invocation above.

**Update to a new version** (deploy only commits whose CI/eval-gate is green):
```bash
git pull
$DC up -d --build            # rebuilds changed images, applies migrations, restarts
curl -s localhost:8000/health
```
Changing the frontend's API URL or the Caddy host requires `--build frontend` (the API base URL
is baked into the bundle at build time).

**Backup before any migration:**
```bash
$DC exec -T db pg_dump -U second_brain second_brain | gzip > backup-$(date +%F).sql.gz
```

**Monitoring (kept private — reach via SSH tunnel from your laptop):**
```bash
ssh -L 3001:localhost:3001 -L 9090:localhost:9090 root@YOUR_VPS_IP
# then open http://localhost:3001 (Grafana) and http://localhost:9090 (Prometheus)
```

---

## Admin / data-ops

`SECOND_BRAIN_ADMIN_TOKEN` is set, so the governed endpoints are **enabled** and require a
bearer token:
- `GET /api/data/export?source_id=…` — export a source (GDPR access).
- `DELETE /api/data/sources/{id}` — delete a source + its documents (GDPR erasure).
- `POST /api/admin/retention/purge` — null `raw_text` past the retention TTL.

```bash
curl -H "Authorization: Bearer <SECOND_BRAIN_ADMIN_TOKEN>" \
  "https://YOUR_VPS_IP.sslip.io/api/data/export?source_id=3"
```

---

The same actions are available in the web UI at `/admin`; paste the admin token into the page
when you need to run one of these guarded operations.

## Security notes / hardening backlog

The deployment is functional and uses real HTTPS, but a few things are worth tightening:

1. **Enable a host firewall.** `ufw` is currently inactive; allow only 22/80/443.
2. **Privacy:** with `SECOND_BRAIN_EMBEDDING_PROVIDER=gemini`, note text is sent to Google at
   **ingest** (not just chat). Switch to `local` embeddings for a fully private path (needs a
   ≥4 GB box for the torch model).

---

## Run locally (dev)

```bash
docker compose up -d db                       # dev compose is db-only (host port 5433)
cd backend && alembic upgrade head && uvicorn app.main:app --reload   # :8000
cd frontend && npm run dev                    # :3000
```
Set `SECOND_BRAIN_GEMINI_API_KEY` (or `SECOND_BRAIN_LLM_PROVIDER=fake` to run without a key).
