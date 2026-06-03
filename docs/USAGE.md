# Second Brain — Usage Guide

How to use and operate the live deployment. Last verified **2026-06-02** against the
production droplet.

---

## Live URLs

> Replace `YOUR_VPS_IP` in the URLs below with your droplet's public IP address.

| What | URL | Notes |
|---|---|---|
| **Web UI** | **https://YOUR_VPS_IP.sslip.io** | Chat + search. Redirects to `/chat`. |
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

### Other endpoints
- `GET /briefing`, `GET /briefing/history` — daily briefings (see below).
- `GET /conversations`, `GET /conversations/{id}` — chat history with reconstructed citations.
- `POST /feedback` — `{"message_id": 123, "rating": 1}` (rating is `1` or `-1`).
- `GET /health` — `{"status":"ok","db":"ok","embedder":"…"}`.

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

## Daily NotebookLM -> Obsidian research

NotebookLM is still a manual study tool. The repeatable workflow is documented in
`docs/notebooklm-to-obsidian-workflow.md`:

1. Ask the question in an Obsidian `Research Brief`.
2. Search Second Brain first and decide whether NotebookLM is needed.
3. Use NotebookLM manually only when long-context source work helps.
4. Paste selected, source-aware output into `NotebookLM Session` or `Source Digest`.
5. Save reviewed Markdown in the vault with `status: draft` or `status: review`.
6. Approve it locally by changing frontmatter to `status: approved`, then reindex it through `/ingest`.
7. Search verify the approved note by title and one important term.

Do not automate NotebookLM, and do not save raw NotebookLM transcripts by default.

---

## Agentic tools (MCP)

The MCP server (`backend/app/mcp_server.py`, stdio) exposes read tools (`search_notes`,
`list_tasks`, `send_digest`) and write tools (`create_task`, `research_topic`) plus
`list_pending_approvals` / `approve_pending_action`. Write tools first return an approval id; set
`SECOND_BRAIN_MCP_WRITE_APPROVAL_TOKEN` and approve the pending action before re-running the write
with that approval id. Wire it into a local MCP client (e.g. Claude Desktop) — run it on the box or
locally with the DB DSN + Gemini key in its `env`. Set `SECOND_BRAIN_LLM_PROVIDER=fake` for a
keyless smoke test.

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
