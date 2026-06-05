# Second Brain — Usage Guide

How to use and operate the local-first app. The optional VPS deployment was last verified
**2026-06-02** against a DigitalOcean droplet, but ADR-0015 changed the default runtime to
local/on-demand Docker Compose on **2026-06-05**.

---

## Local URLs

Use these for normal daily use:

| What | URL | Notes |
|---|---|---|
| **Web UI** | **http://localhost:3000** | Chat, capture, search, ingest, briefing, feedback, tasks, research, sources, admin. Redirects to `/chat`. |
| **API** | http://localhost:8000 | e.g. `/health`, `/chat`, `/search`. |
| **Swagger UI** | http://localhost:8000/docs | Interactive "try it" docs for every endpoint. |
| Metrics | http://localhost:8000/metrics | Prometheus-format app metrics. |

For an optional cloud demo, the old Caddy/VPS path is still
`https://YOUR_VPS_IP.sslip.io` with API calls under `/api`. Treat that as temporary unless you
explicitly choose to pay for always-on hosting again.

---

## What it is

Second Brain is a personal RAG assistant: you **capture** web passages or **ingest** notes/text,
it embeds and stores them in Postgres + pgvector, and you **chat** or **search** over them with
**cited** answers. It also
produces a **briefing** and exposes **agentic tools** over MCP. The LLM (`gemini-2.5-flash`)
can be a hosted Gemini API call, while embeddings can be local MiniLM or hosted Gemini depending
on your privacy/performance setting.

**Architecture:** local-first Docker Compose/processes: `frontend` (Next.js), `api` (FastAPI),
`worker` (briefing and async research), `db` (pgvector), and optional `redis`. The API exposes
Prometheus-format metrics at `/metrics`; Prometheus/Grafana configs are retained under `deploy/`
for optional local/demo monitoring.

---

## Seed the portfolio demo

From `backend/`, seed the compact case-study loop:

```bash
python -m app.demo.seed
```

The seed command creates a capture-backed bookmark, asks a cited chat question, and records
thumbs-down feedback for review. Open `/feedback`, promote the seeded negative example after
checking the labels, then export staged reviewed cases:

```bash
python -m app.eval.export_cases --output eval/promoted-cases.yaml
```

Review the fragment before copying cases into `eval/dataset.yaml`; the running API never mutates
that source-controlled CI fixture.

---

## Using the Web UI

Open **http://localhost:3000**. You get:

- **/chat** — ask a question; the backend buffers generated chunks until citation/support validation
  passes, then sends the answer over SSE and finalizes with inline `[1]`,`[2]` citation markers.
  Click a marker to see the source card (title, snippet, score). A conversation sidebar lists
  past threads (auto-refresh). Thumbs up/down records feedback. A "private mode" toggle routes
  that turn through the local LLM path instead of Gemini (if configured). If the selected LLM
  cannot stream, the UI falls back to the non-streaming `/chat` response.
  When both `SECOND_BRAIN_AGENTIC_RAG_ENABLED=true` and
  `NEXT_PUBLIC_AGENTIC_RAG_ENABLED=true` are set, the composer also shows an agentic RAG toggle.
  Agentic turns use non-streaming `/chat`, plan multiple note searches, and show a compact trace in
  the answer footer.
- **/search** — raw hybrid (vector + full-text) search results with source/tag filters, no LLM.

The browser talks to the local API through `NEXT_PUBLIC_API_BASE_URL` (usually
`http://localhost:8000`). If you set `SECOND_BRAIN_API_TOKEN`, paste the same value into the
sidebar key field so chat, conversations, capture, ingest, search, briefing, feedback, tasks,
research, sources, and admin pages include `Authorization: Bearer ...`.

Additional web pages:
- **/capture** - save a URL, title, selected text, notes, and tags as a searchable bookmark.
- **/ingest** - add manual notes or text documents, with source metadata and tags.
- **/briefing** - read the latest stored briefing and recent briefing history.
- **/feedback** - review thumbs feedback trends, inspect negative examples, edit eval candidates,
  and manually promote reviewed cases into the durable `eval_cases` table. Promotion requires the
  admin token in addition to the normal API bearer.
- **/tasks** - create tasks and mark them open, done, or cancelled.
- **/research** - enqueue async research jobs with optional public source URLs or pasted source
  text, then watch queued/running/done/failed status.
- **/sources** - inspect sources, documents, chunk counts, tags, and retention state.
- **/admin** - run token-guarded export, source delete, and retention purge actions.

---

## Using the API

Base URL for normal use is `http://localhost:8000`. If you temporarily deploy to a VPS, replace
that with `https://YOUR_VPS_IP.sslip.io/api`. Examples use `curl` (works on Windows 11).

Production personal-data APIs require the single-owner API bearer token:

```bash
API_AUTH="Authorization: Bearer <SECOND_BRAIN_API_TOKEN>"
```

This protects `/chat`, `/chat/stream`, `/capture`, `/conversations`, `/ingest`, `/search`, `/briefing`,
`/feedback`, `/tasks`, `/research/jobs`, `/sources`, `/data/*`, and `/admin/*`. `/health`
stays public for uptime checks. Local development remains keyless unless you set
`SECOND_BRAIN_API_TOKEN`; once set, local calls need the same header.

### Capture a web note - `POST /capture`
`/capture` stores browser-provided selected text and notes; it does not fetch or scrape the page
server-side.

```bash
curl -X POST http://localhost:8000/capture \
  -H "$API_AUTH" \
  -H "Content-Type: application/json" -d '{
    "url": "https://example.com/article",
    "title": "Article title",
    "selected_text": "Quoted passage worth keeping.",
    "notes": "Why this matters.",
    "tags": ["inbox", "reading"]
  }'
```

The response returns the created `bookmark` source id, normalized `capture_url`, document status,
content hash, and chunk/embed counts. Re-capturing the same URL with the same selected text and
notes returns `status: "duplicate"`. The web page also accepts query-prefill parameters:
`/capture?url=...&title=...&text=...&notes=...&tags=...`.

### Add notes — `POST /ingest`
`source.type` must be one of: **`manual`**, `notes_folder`, `github`, `rss`, `pdf_upload`,
`bookmark`, `research_note`. Use `manual` for ad-hoc text.

```bash
curl -X POST http://localhost:8000/ingest \
  -H "$API_AUTH" \
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
curl -X POST http://localhost:8000/chat \
  -H "$API_AUTH" \
  -H "Content-Type: application/json" \
  -d '{"message": "How should I tune the HNSW index?"}'
```
Returns `answer` (with `[n]` markers), `citations[]`, token `usage`, `model`, `latency_ms`, and
`conversation_id`. Pass `conversation_id` back to continue a thread. Options:
`{"message":"…","top_k":8,"filters":{"tags":["postgres"]},"options":{"private_mode":false}}`.
If nothing relevant is found it refuses rather than inventing an answer.

Opt-in agentic RAG:

```bash
SECOND_BRAIN_AGENTIC_RAG_ENABLED=true

curl -X POST http://localhost:8000/chat \
  -H "$API_AUTH" \
  -H "Content-Type: application/json" \
  -d '{"message": "How should I tune HNSW for recall and latency?", "options": {"agentic": true}}'
```

Agentic RAG is read-only in v1. It uses LangGraph to plan 2-4 focused searches over existing
indexed notes, merge/dedupe the evidence, optionally retry weak evidence with the original wording,
and answer through the same citation validator as regular chat. The response includes
`retrieval.agentic` with safe trace metadata: subqueries, hit counts, selected chunk count,
fallback/verifier flags, and the step budget. Planner, verifier, and answer calls all use the same
provider choice as the request, including private mode.

### Stream an answer - `POST /chat/stream`
```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "$API_AUTH" \
  -H "Content-Type: application/json" \
  -d '{"message": "How should I tune the HNSW index?"}'
```
Uses the same request body as `/chat`, but returns Server-Sent Events:

- `event: delta` with `{"text":"..."}` chunks only after the assembled answer has passed citation
  and support validation. Uncited, invalidly cited, or weakly supported model text is withheld and replaced by the final
  citation-failure response.
- `event: complete` with the same JSON shape as `/chat`, including final `citations[]`,
  `usage`, `model`, `latency_ms`, and `conversation_id`.
- `event: error` if streaming fails after the response has started.

If the selected LLM provider cannot stream, the endpoint returns `409` before starting SSE; clients
should call `/chat` as a fallback. Gemini, Ollama, and the test fake driver currently implement the
streaming interface.

Agentic RAG does not stream in v1. `/chat/stream` returns `409` when `options.agentic=true`; clients
should call `/chat` so no answer text is delivered before citation validation.

### Search — `GET /search`
```bash
curl -H "$API_AUTH" "http://localhost:8000/search?q=hnsw+tuning&top_k=5"
```

### Redis-backed safeguards and caches
Production Compose enables Redis for three conservative hot paths:

- `POST /chat`, `POST /chat/stream`, `POST /capture`, and `POST /ingest` use fixed-window API rate limits keyed by client IP.
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
| `SECOND_BRAIN_RATE_LIMIT_FAIL_CLOSED` | `true` |
| `SECOND_BRAIN_SEARCH_CACHE_ENABLED` | `true` |
| `SECOND_BRAIN_SEARCH_CACHE_TTL_SECONDS` | `120` |
| `SECOND_BRAIN_EMBEDDING_CACHE_ENABLED` | `true` |
| `SECOND_BRAIN_EMBEDDING_CACHE_TTL_SECONDS` | `604800` |

Redis cache failures are best-effort and fall back to Postgres/LLM. Rate-limit failures fail closed
by default when Redis is enabled; set `SECOND_BRAIN_RATE_LIMIT_FAIL_CLOSED=false` only as an
explicit availability trade-off. `/metrics` exposes `cache_events_total` and
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
  cases. `expected_docs` is inferred from cited documents; nothing is promoted automatically.
- `POST /feedback/eval-candidates/{feedback_id}/promote` - persist one reviewed case in Postgres
  as a durable `eval_cases` row. This also requires `X-Second-Brain-Admin-Token`; the body must
  confirm expected sources, expected keywords, and refusal behavior.

Additional API endpoints:
- `GET /sources`, `GET /sources/{id}/documents` - source and document overview.
- `GET /tasks`, `POST /tasks`, `PATCH /tasks/{id}` - task list and status updates.
- `POST /research/jobs`, `GET /research/jobs`, `GET /research/jobs/{id}` - queued source-backed
  research jobs.

### Feedback analytics and eval candidates
Use feedback analytics to turn thumbs into reviewable quality data:

```bash
curl -H "$API_AUTH" "http://localhost:8000/feedback/analytics?days=30"
curl -H "$API_AUTH" "http://localhost:8000/feedback/negative?limit=25&days=30"
curl -H "$API_AUTH" "http://localhost:8000/feedback/eval-candidates?limit=25&days=30"
```

Eval candidate responses mirror the fixed eval dataset shape, but remain review-only:

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

Promote exactly one reviewed candidate after editing the labels:

```bash
curl -X POST http://localhost:8000/feedback/eval-candidates/123/promote \
  -H "$API_AUTH" \
  -H "X-Second-Brain-Admin-Token: <SECOND_BRAIN_ADMIN_TOKEN>" \
  -H "Content-Type: application/json" -d '{
    "id": "feedback-123-reviewed",
    "question": "What should this answer have covered?",
    "expected_docs": ["FastAPI backend"],
    "expected_keywords": ["/feedback"],
    "expect_refusal": false,
    "confirmations": {
      "expected_docs": true,
      "expected_keywords": true,
      "expect_refusal": true
    }
  }'
```

Promotion is manual, admin-gated, audited, and validation is strict: promoted cases include a
strict `review` block with the feedback id, reviewer identity, timestamp, and confirmation flags.
`expected_docs` must be fixed eval corpus document titles, refusal cases must have empty
`expected_docs` and `expected_keywords`, malformed cases return `422`, and duplicate races return
`409` without changing `backend/eval/dataset.yaml`. Promotion stores the reviewed case durably in
Postgres (`dataset_path: "postgres:eval_cases"`). The source-controlled fixed dataset remains the
CI gate artifact, so promoted cases are staged for a deliberate repo change rather than written
from the production container.

Export staged reviewed cases from `backend/`:

```bash
python -m app.eval.export_cases --output eval/promoted-cases.yaml
```

### Source-backed research - `POST /research/jobs`
Research does not use a paid search API. Provide your own evidence as public URLs or source text;
the worker fetches/parses safe public text/HTML URLs on default HTTP(S) ports only, asks the configured LLM to ground the note
in those excerpts, stores a `research_note`, and writes provenance into the stored document
metadata.

```bash
curl -X POST http://localhost:8000/research/jobs \
  -H "$API_AUTH" \
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

## Briefing

The worker drains a Postgres-backed job queue. In local-first mode, run the worker when you want
briefings or async research jobs processed, and enqueue a briefing manually or with Windows Task
Scheduler while your machine is on. Read the result at `GET /briefing`. Each run summarizes
documents ingested since the previous briefing.

From `backend/`, with the backend environment loaded:

```bash
python -m app.jobs.enqueue briefing
python -m app.jobs.worker --once
```

For an optional VPS/cloud demo, use the Compose command in the deploy runbook instead.

---

## Agentic tools (MCP)

The MCP server (`backend/app/mcp_server.py`, stdio) exposes five tools: `search_notes`,
`create_task`, `list_tasks`, `send_digest`, and `research_topic`. MCP clients run as trusted local
processes with direct DB/service access, so durable mutations are disabled by default. Set
`SECOND_BRAIN_MCP_ENABLE_MUTATIONS=true` only for a trusted local client before using `create_task`
or `research_topic`.

`research_topic(topic, source_urls?, source_texts?)` accepts optional public URLs or pasted snippets,
stores the grounded note as a `research_note`, auto-indexes it, and returns `evidence_count` plus
`sources[]` provenance. Wire it into a local MCP client (e.g. Claude Desktop) - run it on the box or
locally with the DB DSN + Gemini key in its `env`. Set `SECOND_BRAIN_LLM_PROVIDER=fake` for a
keyless smoke test.

---

## Optional Cloud Operations

The commands below are only for a temporary VPS/cloud demo. They are not required for normal
local-first use.

```bash
ssh root@YOUR_VPS_IP
cd /root/second-brain

# the stack is ONE project; always pass -p second-brain + BOTH compose files + the env file:
DC="docker compose -p second-brain -f deploy/docker-compose.prod.yml -f deploy/docker-compose.vps.yml --env-file deploy/.env.prod"

$DC ps                       # status of the stack services
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

**Production environment variables:**

| Variable | Required | Purpose |
|---|---:|---|
| `POSTGRES_PASSWORD` | Yes | Database password for the self-hosted Postgres service. |
| `SECOND_BRAIN_API_TOKEN` | Yes | Single-owner bearer token for personal-data routes and normal web/API use. |
| `SECOND_BRAIN_ADMIN_TOKEN` | Recommended for data-ops and eval promotion | Enables export, source deletion, retention purge, and durable eval-case promotion when sent as `X-Second-Brain-Admin-Token` alongside the normal API bearer. Leave blank to return 503 from governed endpoints. |
| `SECOND_BRAIN_GEMINI_API_KEY` | For real Gemini mode | Required when `SECOND_BRAIN_LLM_PROVIDER=gemini`; omit only for `fake` or local Ollama mode. |
| `SECOND_BRAIN_MCP_ENABLE_MUTATIONS` | Optional local MCP | Defaults to `false`; set `true` only for trusted local MCP clients that may create tasks or research notes. |
| `SECOND_BRAIN_AGENTIC_RAG_ENABLED` | Optional RAG experiment | Defaults to `false`; set `true` to allow `/chat` requests with `options.agentic=true`. |
| `NEXT_PUBLIC_API_BASE_URL` | Yes | Browser-visible API base, usually `http://localhost:8000` locally or `https://YOUR_VPS_IP.sslip.io/api` for an optional cloud demo. |
| `NEXT_PUBLIC_AGENTIC_RAG_ENABLED` | Optional web toggle | Defaults to hidden/false; set `true` only when the backend agentic flag is also enabled. |

**Health checks:**
```bash
curl -fsS localhost:8000/health
curl -fsS http://localhost:8000/health
$DC ps
$DC exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
$DC exec -T redis redis-cli ping
sudo ufw status verbose
```

**Backup before any migration:**
```bash
$DC exec -T db pg_dump -U second_brain second_brain | gzip > backup-$(date +%F).sql.gz
```

Automated nightly backups are installed through `/etc/cron.d/second-brain-backup` and run
`/usr/local/sbin/second-brain-backup`, which is sourced from `deploy/cron/second-brain-backup`.
See `docs/runbooks/backup-restore.md` for restore and monthly restore-drill commands.

**Rollback:**
```bash
git checkout <previous-green-sha>
$DC up -d --build
curl -fsS localhost:8000/health
```

For migrations, restore the pre-migration dump unless the Alembic downgrade was tested. For prompt
regressions, set `SECOND_BRAIN_PROMPT_VERSION=rag-v1` in `deploy/.env.prod` and recreate `api`.

**Monitoring:**
The production stack exposes app metrics on the private API port. Use this directly for quick checks:
```bash
DC="docker compose -p second-brain -f deploy/docker-compose.prod.yml -f deploy/docker-compose.vps.yml --env-file deploy/.env.prod"
curl -fsS localhost:8000/metrics | head
```
Prometheus/Grafana configs remain in `deploy/prometheus/` and `deploy/grafana/`, but production
Compose no longer includes monitoring containers because the current upstream vendor images scanned
with critical/high CVE findings. Reintroduce monitoring only with scanned-clean images or custom
builds.

## Retiring the DigitalOcean droplet

You can retire the current droplet once all of these are true:

1. Local startup works: backend health returns OK at `http://localhost:8000/health`, the frontend
   opens at `http://localhost:3000`, and you can search/chat against the local database you intend
   to keep.
2. You have a fresh Postgres dump from the droplet and have restored or archived it somewhere
   local/trusted.
3. Any useful files from `/root/second-brain/deploy/.env.prod`, local uploads, backup archives,
   and screenshots/evidence have been copied off the droplet.
4. You no longer need the public `https://YOUR_VPS_IP.sslip.io` demo URL.

Stopping/powering off a DigitalOcean droplet does **not** end Droplet billing because its compute
resources remain reserved. After the backup is safely copied and verified, destroy the droplet and
remove any unattached volumes, snapshots, reserved IPs, load balancers, or firewall resources you
no longer need.

---

## Admin / data-ops

`SECOND_BRAIN_ADMIN_TOKEN` enables the governed endpoints. They first pass the normal
`SECOND_BRAIN_API_TOKEN` gate, then require the admin token for the destructive/read-all action.
Use the normal API bearer plus the separate admin header for these calls:
- `GET /api/data/export?source_id=…` — export a source (GDPR access).
- `DELETE /api/data/sources/{id}` — delete a source + its documents (GDPR erasure).
- `POST /api/admin/retention/purge` — null `documents.raw_text` past the retention TTL while
  leaving searchable chunks intact.
- `POST /api/feedback/eval-candidates/{feedback_id}/promote` — store a reviewed case in the
  durable `eval_cases` table.

```bash
curl -H "Authorization: Bearer <SECOND_BRAIN_API_TOKEN>" \
  -H "X-Second-Brain-Admin-Token: <SECOND_BRAIN_ADMIN_TOKEN>" \
  "http://localhost:8000/data/export?source_id=3"
```

---

The same data-ops actions are available in the web UI at `/admin`; eval promotion is available in
`/feedback`. Paste the admin token into the page only when you need to run one of these guarded
operations.

## Security notes / hardening

The deployment is functional, uses real HTTPS, and should run with a host firewall:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status verbose
```

Only SSH and Caddy should be public. Do not expose 3000, 8000, Postgres, or Redis to the internet;
the base Compose file and VPS override bind those direct ports to `127.0.0.1`. If monitoring
containers are reintroduced later, keep their ports private as well.

Secret rotation lives in `docs/runbooks/incident-response.md`: rotate Gemini/API/admin/Grafana
secrets by updating `deploy/.env.prod` plus the password manager and recreating the affected
services; rotate `POSTGRES_PASSWORD` directly in Postgres and recreate `api`/`worker`.

1. **Auth:** this is intentionally single-owner bearer-token auth, not multi-user accounts. The
   frontend stores the normal API token in browser local storage so local/dev use stays simple and
   no paid provider or cookie/session service is required. Treat the browser profile as holding a
   bearer secret; rotate `SECOND_BRAIN_API_TOKEN` if the machine or browser profile is compromised.

1. **Capture URL handling:** `/capture` validates URLs but does not fetch them server-side. It
   rejects non-HTTP(S), credentialed, localhost, and literal private/internal IP URLs before saving
   the capture. If server-side fetching is added later, use the DNS-pinned public URL fetch pattern
   from source-backed research rather than turning capture into a scraper.

1. **Privacy:** with `SECOND_BRAIN_EMBEDDING_PROVIDER=gemini`, note text is sent to Google at
   **ingest** (not just chat). During chat, retrieved chunks and the user question are sent to the
   configured generation provider. Switch to `local` embeddings and local Ollama generation for
   the private path, with the trade-off that your local machine needs more memory. Retention nulls only the
   original `documents.raw_text` copy; `chunks.content` remains searchable until source erasure.
   Agentic RAG uses the same provider choice for planning, verification, and answering, but it can
   send more search queries and retrieved snippets to that provider during one turn.

---

## Run locally (dev)

```bash
docker compose up -d db                       # dev compose is db-only (host port 5433)
cd backend && alembic upgrade head && uvicorn app.main:app --reload   # :8000
cd frontend && npm run dev                    # :3000
```
Set `SECOND_BRAIN_GEMINI_API_KEY` (or `SECOND_BRAIN_LLM_PROVIDER=fake` to run without a key).
Do not set `SECOND_BRAIN_API_TOKEN` locally unless you want to test the production auth path; when
you do set it, paste the same token into the web sidebar or send `Authorization: Bearer ...`.
