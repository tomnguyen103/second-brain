# Progress Log — Second Brain

Running log of what's done, in progress, and next. Keep this current at the end of each
session — the master prompt treats it as the source of truth for "where we are."

## Status at a glance

| Phase | Description | Status |
|---|---|---|
| Planning | Project design, stack, cost model, roadmap | ✅ Complete |
| 0 | Data model + ER diagram + Alembic migrations + pgvector/full-text indexes | ✅ Complete |
| 1 | RAG MVP: FastAPI /ingest + /chat, hybrid retrieval, Gemini via LLMClient | ✅ Complete |
| 2 | Next.js chat UI (streaming, citations, semantic search, feedback) | ✅ Complete |
| 3 | Evaluation + MLOps: eval set, MLflow, A/B, prompt versioning + rollback | ✅ Complete |
| 4 | MCP server + agentic actions incl. self-research tool | ✅ Complete |
| 5 | Daily briefing + scheduled pipelines | ✅ Complete |
| 6 | Productionize on VPS + data-ops hardening | ✅ Complete |
| 7 | Kubernetes learning track on local k3s/kind | ✅ Complete |

Legend: ⬜ not started · 🟡 in progress · ✅ complete

## Session log

Add a dated entry per working session. Most recent on top.

### 2026-06-05 - Security review findings fixed
- **What:** fixed the follow-up findings from the security review: the admin token no longer passes
  the normal API gate, destructive data-ops now require both the API bearer and
  `X-Second-Brain-Admin-Token`, MCP durable mutations are disabled unless
  `SECOND_BRAIN_MCP_ENABLE_MUTATIONS=true`, chat rejects unsupported cited answer segments, and
  research URL fetches accept only default HTTP(S) ports.
- **Docs:** updated README, `docs/USAGE.md`, deploy env comments, runbooks, and implementation
  notes with the new two-header admin flow, MCP trust boundary, citation-support trade-off, and
  research URL restriction.
- **Verified:** focused auth/data-ops/MCP/config/research/chat/API tests passed
  (`31 passed, 21 skipped, 1 warning`); full DB-backed backend suite passed
  (`226 passed, 6 warnings`); frontend lint and production build passed; `npm audit` reported zero
  moderate-or-higher vulnerabilities; production Compose config rendered with dummy secrets; and
  `git diff --check` reported only existing CRLF normalization warnings.

### 2026-06-05 - Frictionless web capture added
- **What:** added an authenticated `/capture` API plus a `/capture` web page for saving a URL,
  title, selected text, notes, and tags into the existing ingest/source/document pipeline as a
  `bookmark` capture. Captured content is chunked, embedded, full-text indexed, visible through
  sources/search, and citeable by chat like any other ingested document.
- **Safety/design:** capture does not fetch or scrape the remote page server-side. It stores the
  browser/user-provided selected text and notes, rejects non-HTTP(S), credentialed, localhost, and
  literal private/internal IP URLs, and records the no-scrape trade-off in implementation notes.
- **Frontend:** added `/capture` to the sidebar, typed `api.capture`, and query-parameter prefill
  support for `url`, `title`, `text`, `notes`, and `tags` so a bookmarklet/share shortcut can hand
  off to the page later without extra infrastructure.
- **Verified:** focused capture/auth tests passed (`28 passed, 1 warning`); full backend suite
  passed (`221 passed, 6 warnings`) against local pgvector on `localhost:5433`; `npm run lint` and
  `npm run build` passed, with the existing Next.js multiple-lockfile workspace-root warning.

### 2026-06-05 - High security finding fixed: validated SSE chat
- **What:** fixed the high-severity security review finding where `/chat/stream` could emit raw
  model deltas before citation validation. The backend now buffers provider chunks, runs the shared
  citation validation/finalization path, and emits SSE `delta` chunks only for answers that passed
  validation. Uncited or invalidly cited model text is withheld and replaced by the
  citation-failure completion.
- **Tests:** added service-level and API-level regressions with a fake streaming LLM that emits
  `SECRET_STREAM_LEAK` without citations; both assert the text never appears in deltas or the SSE
  body.
- **Docs:** updated README, `docs/USAGE.md`, and implementation notes to document the new
  confidentiality-over-token-streaming trade-off.
- **Verified:** focused streaming/API tests passed (`14 passed, 1 warning`); full backend suite
  passed (`212 passed, 6 warnings`) against local pgvector on `localhost:5433`; `git diff --check`
  passed with only existing CRLF normalization warnings.

### 2026-06-05 - Single-owner authentication finalized
- **What:** completed simple no-cost bearer-token authentication for the personal Second Brain
  surface. `SECOND_BRAIN_API_TOKEN` now protects chat/streaming chat, conversations, ingest,
  search, briefing, feedback, tasks, research jobs, sources, and admin/data-ops routes whenever the
  token is configured; keyless local development is preserved when it is unset.
- **Admin guard:** destructive/read-all data-ops routes (`/data/export`, `/data/sources/{id}`,
  `/admin/retention/purge`) now pass the normal API gate and still require
  `SECOND_BRAIN_ADMIN_TOKEN` as an additional admin header.
- **Docs:** updated README, `docs/USAGE.md`, env templates, and implementation notes with production
  auth variables, local-dev behavior, and the browser-local-storage bearer-token trade-off.
- **Verified:** auth unit coverage passed (`19 passed`); DB-backed data-ops integration passed
  (`6 passed`); focused auth/chat/API/briefing/dataops set passed (`42 passed`); full backend suite
  passed (`210 passed, 6 warnings`) against local pgvector on `localhost:5433`; `npm run lint`,
  `npm run build`, `git diff --check`, production Compose config rendering, and config unit tests
  passed. `npm run build` still emits the existing Next.js multiple-lockfile workspace-root warning.

### 2026-06-05 - Security review fixes applied
- **What:** hardened the current local changes after a security review. User-data APIs now support
  single-user bearer API-token protection while keeping keyless local development possible; the
  frontend has an API-key entry point; admin-token checks use constant-time comparison; CORS no
  longer allows credentials; streaming SSE errors return a generic failure; Redis rate limits fail
  closed by default and ignore `X-Forwarded-For` unless explicitly trusted.
- **Data/security:** research URL fetches now validate DNS-resolved public IPs and every redirect to
  reduce SSRF and DNS-rebinding risk. RAG prompts mark retrieved notes as untrusted context, and
  uncited or invalidly cited answers are replaced with a weak-context refusal before persistence.
- **Ops:** production Compose now requires explicit Postgres/API/admin secrets, binds direct service
  ports to localhost, removes PgBouncer from the production runtime, builds a custom pgvector image,
  uses prod-only backend requirements with CPU-only Torch, keeps local `.env.*` files out of Docker
  build contexts, removes vulnerable Prometheus/Grafana runtime containers from production Compose
  while retaining metrics/config artifacts, uses a patched custom Caddy image, and documents
  rotation, restore, and backup expectations in the runbooks.
- **CI/local/K8s:** local dev Compose and GitHub integration/eval jobs now use the repo's cleaned
  pgvector image instead of the public pgvector image. The Kubernetes learning-track default apply
  now runs the core stack only, uses local pgvector, connects API/worker directly to Postgres,
  carries `SECOND_BRAIN_API_TOKEN`, and gates PgBouncer/Prometheus/Grafana templates behind local
  `*-clean-required` images.
- **Verified:** focused backend security unit tests passed (27 passed) and focused backend
  integration tests passed (33 passed); `npm audit --audit-level=moderate`, `npm run lint`,
  `npm run build`, `bash -n deploy/cron/second-brain-backup`, `git diff --check`, Compose config
  validation, `kubectl kustomize deploy/k8s`, GitHub workflow YAML parsing, Dockerfile static
  checks for backend/frontend/pgvector, Caddy config validation, and Docker Scout critical/high
  scans for the runtime images (`api`, `frontend`, custom pgvector, custom Caddy, Redis) passed.
  The final closeout rerun of `docker buildx build --check -f deploy/Dockerfile.caddy .` was blocked
  by Docker Hub rate limiting while resolving `golang:1.26.4-alpine`; the same Caddy static check
  passed earlier in the session. `pip-audit` was not run because it is not installed in the backend
  virtualenv.
- **Remaining:** no open blocker from this security pass; reintroducing on-box Prometheus/Grafana is
  a future task that should use scanned-clean images or custom builds.

### 2026-06-04 - Local streaming and ops changes stabilized for review
- **What:** inspected the full uncommitted diff on `main` and verified the local review surface:
  SSE streaming chat, README/USAGE/runbook updates, env-template/gitignore hygiene, the VPS backup
  cron template, and the ops runbooks. No unrelated local changes were reverted.
- **Outcome:** no functional code changes were needed beyond this progress closeout; the existing
  local changes remain scoped to streaming chat, local env hygiene, backup/restore operations, and
  README/docs synchronization.
- **Verified:** focused backend tests passed
  (`tests/unit/test_chat_stream.py`, `tests/integration/test_chat.py`,
  `tests/integration/test_api.py`, `tests/integration/test_briefing.py`); `npm run lint` passed;
  `npm run build` passed with the existing Next.js multiple-lockfile workspace-root warning;
  `git diff --check` passed; `bash -n deploy/cron/second-brain-backup` passed; the VPS Compose
  example rendered with `docker compose ... config`.

### 2026-06-04 - README refreshed with latest operations and streaming state
- **What:** updated `README.md` so the repository overview now reflects the latest production
  operations hardening, streaming chat, local environment hygiene, current capabilities, and
  follow-ups.
- **Tone/layout:** kept the professional portfolio structure while refreshing the current-status,
  recent-updates, capabilities, deploy, cost/privacy, and known-follow-ups sections.
- **Verified:** README consistency checks and diff review were run in this session.

### 2026-06-04 - Production operations hardening runbooks
- **What:** hardened the VPS operations docs with `ufw` allow-list steps for 22/80/443 only,
  health-check command blocks, automated Postgres backup cron installation, monthly restore-drill
  procedure, secret rotation steps, and app/migration/prompt rollback guidance.
- **Deploy/docs:** added `deploy/cron/second-brain-backup` as the installable backup script
  template, noted the firewall expectation in the VPS Compose example, and updated
  `docs/USAGE.md` plus the deploy, backup/restore, and incident-response runbooks.
- **Verified:** docs consistency and Compose config validation were run in this session.

### 2026-06-04 - Local API key entry point documented and ignored
- **What:** clarified the local Gemini API key location in `backend/.env.example`, added a
  frontend API-base template at `frontend/.env.example`, and tightened root/frontend `.gitignore`
  rules so real `.env` / `.env.*` files stay out of Git while `.env.example` templates remain
  commit-able.
- **Verified:** checked ignore status so local `backend/.env` and `frontend/.env.local` remain
  untracked/private.

### 2026-06-04 - SSE streaming chat shipped
- **What:** added a streaming-capable LLM interface (`generate_stream`) with Gemini, Ollama, and
  fake-driver implementations; added `POST /chat/stream` as SSE while preserving the existing
  non-streaming `POST /chat`; shared the retrieval/finalization path so persisted assistant
  messages, retrieval rows, and final citations match the JSON endpoint.
- **Frontend:** `/chat` now streams assistant deltas via `fetch()` SSE parsing, finalizes with the
  normal `ChatResponse` payload so citation cards and feedback still work, and falls back to
  `/chat` when the stream endpoint reports that the selected provider cannot stream.
- **Tests/docs:** added SSE framing and stream completion coverage, documented `/chat/stream` in
  `docs/USAGE.md`, and stabilized a briefing integration test timestamp window that was flaky
  against the local Postgres clock.
- **Verified:** backend suite passed against local pgvector (`187 passed, 6 warnings`);
  `npm run lint` passed; `npm run build` passed with the existing Next.js multiple-lockfile
  workspace-root warning.

### 2026-06-04 - README synchronized with live state and professionalized
- **What:** refreshed `README.md` into a cleaner portfolio-grade layout with current status,
  recent updates, product capabilities, user surfaces, tech stack, roadmap, production
  architecture, local run steps, deploy summary, Kubernetes learning-track notes, and follow-ups.
- **Sync fixes:** reordered recent updates so PRs #16/#15 appear ahead of the live-deploy work;
  clarified the live stack as 8 base production services + Caddy = 9 services; replaced stale
  fixed cost language with provider-neutral "one small VPS" wording while noting the verified
  2 GB DigitalOcean deployment; resolved the PR after the app-surface and Redis work landed so
  the README now reflects those completed paths instead of listing them as follow-ups.
- **Verified:** resolved the merge conflict against `main`; docs-only diff passed
  `git diff --check`.

### 2026-06-04 - Redis-backed rate limits and caches
- **What:** added optional Redis paths for the production stack: fixed-window `/chat` and `/ingest`
  API rate limiting, short-lived `/search` response caching with ingest-driven epoch invalidation,
  and hashed-text embedding caching for ingest chunks and retrieval query vectors.
- **Config/ops:** local development keeps Redis disabled by default; prod Compose now sets
  `SECOND_BRAIN_REDIS_ENABLED=true` and `SECOND_BRAIN_REDIS_URL=redis://redis:6379/0`. Redis
  failures fail open and log/emit cache or rate-limit metrics instead of taking the API down.
- **Tests/docs:** added fake-Redis unit tests for cache/rate-limit behavior and route wiring.
  Updated `docs/USAGE.md` and recorded the fail-open trade-off in implementation notes.
- **Verified:** Redis-focused tests passed (`9 passed`); full backend suite passed
  (`184 passed, 6 warnings`) against local pgvector on `localhost:5433`; prod Compose config
  validated with `docker compose -f deploy/docker-compose.prod.yml config`.

### 2026-06-04 - Feedback analytics + eval-candidate review workflow
- **What:** turned stored thumbs feedback into quality data: `GET /feedback/analytics` summarizes
  totals, daily trends, model stats, and top negatively cited documents; `GET /feedback/negative`
  lists negative feedback with conversation, message, previous user question, answer, retrieval,
  and reconstructed citation context; `GET /feedback/eval-candidates` exports negative examples
  as review-first eval candidate cases.
- **Frontend/docs:** added a `/feedback` review page to the existing app shell and sidebar, plus
  API client/types for analytics, negative review items, and eval candidates. Updated
  `docs/USAGE.md` and recorded the review-first candidate trade-off in implementation notes.
- **Tests:** added integration coverage for analytics deltas, negative context payloads, and
  eval-candidate export.
- **Verified:** backend suite passed (`175 passed, 6 warnings`) against the local pgvector DB on
  `localhost:5433`; `npm run lint` passed; `npm run build` passed with the existing Next.js
  multiple-lockfile workspace-root warning.

### 2026-06-04 - Retrieval quality threshold + weak-context refusal
- **What:** added a configurable vector relevance threshold before hybrid RRF fusion, plus
  no-LLM refusal when retrieval has no usable context after filtering. Exact full-text matches
  still pass through, so rare-term lookup is preserved.
- **Retrieval/eval:** added an optional query rewrite hook behind config (disabled by default),
  expanded the eval dataset from one to three refusal probes, and made the eval pipeline use the
  same weak-context refusal path as chat.
- **Tests:** added focused threshold/refusal/rewrite tests and updated eval dataset/harness tests.
- **Verified:** backend suite passed (`172 passed, 6 warnings`) against the local pgvector DB on
  `localhost:5433`; `python -m app.eval.gate` passed with `hit_at_k=1.000`,
  `citation_validity=1.000`, `refusal_accuracy=1.000`.

### 2026-06-04 - Self-research upgraded to source-backed notes
- **What:** upgraded `research_topic` so research can be grounded in user-provided source text
  and safe public text/HTML URLs without adding a paid search API. The service now builds a
  source-constrained prompt, appends a deterministic `## Sources` section to stored notes, and
  records source provenance in `documents.metadata`.
- **Backend:** MCP `research_topic` now accepts `source_urls` and `source_texts` and returns
  `evidence_count` plus `sources[]`; queued research jobs persist those inputs and the worker
  returns the same provenance in `payload.result`.
- **Frontend/docs:** `/research` can enqueue source URLs and pasted source text. `docs/USAGE.md`
  documents the REST/MCP source-backed workflow and provenance fields.
- **Verified:** DB-free research/MCP unit tests passed (`5 passed`). Focused integration tests
  against the live local pgvector DB with `SECOND_BRAIN_LLM_PROVIDER=fake` passed (`11 passed`
  across research storage, job handlers, and research job API); this confirms the keyless fake-LLM
  path still works.

### 2026-06-04 - Backend capabilities promoted into first-class web UI pages
- **What:** added modern operational web pages and sidebar navigation for `/ingest`, `/briefing`,
  `/tasks`, `/research`, `/sources`, and `/admin`, keeping the existing amber/zinc UI language,
  React Query data loading, skeleton/empty/error states, and token-entry guard for admin actions.
- **Backend:** added minimal REST wrappers where the domain already existed: `/tasks` over the
  MCP task service, `/research/jobs` over the durable `jobs` table, and `/sources` +
  `/sources/{id}/documents` over existing source/document/chunk/tag models. Existing briefing,
  ingest, data-ops, search, chat, conversation, and feedback endpoints stayed intact.
- **Frontend:** updated `frontend/lib/api/{client,types}.ts`, added shared page scaffolding, and
  kept `/chat` history behavior while refactoring its history hydration to satisfy the React hook
  lint rule. Also fixed the sidebar theme-mounted hook lint issue that blocked the requested gate.
- **Docs:** updated `docs/USAGE.md` for the new web routes and API endpoints.
- **Verified:** local pgvector DB started, migrations current, touched API tests passed
  (`16 passed` across tasks/research/sources/briefing/dataops API tests). `npm run lint` passed.
  `npm run build` passed; Next emitted its existing multiple-lockfile workspace-root warning.

### 2026-06-02 — LIVE on the VPS: full stack up + Caddy HTTPS, end-to-end verified
- **What:** brought the production stack fully live on the **DigitalOcean droplet**
  (`YOUR_VPS_IP`, 2 GB, project **`second-brain`**, files `docker-compose.prod.yml` +
  `docker-compose.vps.yml`, embeddings offloaded to Gemini so it fits 2 GB). Added a **Caddy**
  reverse proxy with **real Let's Encrypt HTTPS** via the no-domain host
  **`YOUR_VPS_IP.sslip.io`** (`/api/*` → api, everything else → frontend; http→https 308).
  New files: `deploy/caddy/Caddyfile`, `deploy/docker-compose.vps.yml`, `docs/USAGE.md`.
- **Found the API live but only 4/8 services up** (api, db, pgbouncer, redis); frontend, worker,
  grafana, prometheus stuck in **Created**. Root cause: the `vps.yml` override **added** a
  `127.0.0.1:` port to prometheus/grafana, and **compose concatenates port lists** rather than
  replacing — so each tried to bind both `0.0.0.0:PORT` and `127.0.0.1:PORT` → "address already
  in use" (exit 128), which aborted the `up` and left the rest Created. **Fix:** `ports: !override`
  in the override (compose v2.24+ tag) so the localhost binding replaces the base one.
- **Two more fixes:** (1) the frontend image baked `NEXT_PUBLIC_API_BASE_URL` at **build** time
  but the override only passed it as `build.args` (correct) — rebuilt with the HTTPS `/api` URL so
  the browser bundle isn't mixed-content; (2) documented the **project-name gotcha**: omitting
  `-p second-brain` resolves the project to `deploy` and spins up an empty duplicate (hit it once,
  cleaned it up incl. orphan volumes).
- **Verified end-to-end over HTTPS** (real cert, from off-box): `/api/health` ok; `/ingest`
  (`type:manual` — `note` violates `sources_type_check`) embedded via Gemini; `/search` retrieved
  it; `/chat` returned a **cited** `gemini-2.5-flash` answer (1.4 s); `/briefing` produced a
  Gemini briefing after enqueue. All 8 app services + caddy **Up**; cert auto-renews (exp 2026-08-31).
- **Ops wired:** daily briefing **cron** installed at `/etc/cron.d/second-brain-briefing` (07:00,
  correct `-p second-brain` invocation — the runbook's old line would've hit the project-name bug).
  Grafana/Prometheus stay bound to `127.0.0.1` (SSH-tunnel only). PR #14 follow-up also made the
  VPS override bind direct API/frontend ports to `127.0.0.1`, leaving Caddy 80/443 as the public surface.
- **PR #14 verification fix:** the fresh head reproduced the Phase-7 `kind-smoke` ingress-nginx
  admission webhook race twice (`connect: connection refused` during `kubectl apply -k`). Patched
  `.github/workflows/k8s.yml` to retry the apply through that transient readiness gap.
- **Known follow-ups:** briefing `body_markdown` has mojibake em-dash/middot (cosmetic, app-code,
  spawned as a separate task); enable `ufw` (USAGE.md §hardening).

### 2026-06-02 — Live deploy validated LOCALLY on Docker Desktop (prod Compose stack) + Gemini model fix
- **What:** brought up `deploy/docker-compose.prod.yml` end-to-end on Docker Desktop (project
  `second-brain-prod`, isolated from the dev DB on 5433) with a real Gemini API key — running the
  Phase-6 live-deploy runbook locally before provisioning a VPS (chose "run locally first").
- **Fix (see implementation-notes):** Google **retired `gemini-1.5-flash`** on the API (first real
  `generateContent` call 404'd — prior phases only used the `fake` driver, so the model name was never
  live-tested). Bumped the default to **`gemini-2.5-flash`** (GA, pinned for eval reproducibility) in
  `app/config.py` + `app/llm/gemini.py`, and wired a `SECOND_BRAIN_GEMINI_MODEL` passthrough into the
  api+worker in the prod compose so it's swappable via `.env.prod`. api+worker rebuilt (torch layer
  cached → seconds).
- **Verified:** all 8 services Up; migrations `0001`→`0004`; `/health` `db:ok` (PgBouncer
  scram-sha-256); ingest (`embedded=1`) → `/chat` cited answer on `gemini-2.5-flash` (147 prompt / 321
  total tokens, ~1.6 s); frontend HTTP 200; Grafana `database:ok`; Prometheus Ready; worker drained a
  `briefing` job → stored a Gemini-written digest. **Local validation only — not committed.**
- **Next:** for always-on, provision the VPS (ADR-0011: Oracle Cloud Always Free SG primary / Contabo
  SG ~$5 fallback) and run `docs/runbooks/deploy-checklist.md` — the model fix is in the code now so it
  won't recur there. Optional: branch + PR the model fix.

### 2026-06-02 — Phase 7 COMPLETE: Kubernetes learning track on local kind (manifests + HPA + ingress + CI/CD), torn down
- **Branch:** `phase-7-impl` (off main, Phase 5 merged via PR #10). Plan in `docs/phase-7-plan.md`;
  decisions in **ADR-0014**. NOT pytest-TDD — verification is "apply manifest → assert rollout/health/
  scale", captured as text under **`docs/k8s-evidence/`** (00 overview + 01–09 per layer + 11 teardown).
- **What shipped (`deploy/k8s/`):** real manifests translating all **8** prod-compose services —
  Postgres **StatefulSet + PVC** (+ headless Service), a one-shot **migrate Job** (`alembic upgrade
  head` direct to the DB, split out of the api's compose command, D3), **pgbouncer** (env-configured
  so no `userlist.txt`/password is committed, D12), **redis**, **api** (uvicorn only; CPU requests for
  HPA), **worker** (`--loop`), **frontend** (NEXT_PUBLIC baked at build, D11), **ingress-nginx**
  host-based routing (`api.second-brain.local` / `second-brain.local`), **metrics-server + HPA** on
  api CPU, and **Prometheus + Grafana** (configs reused `--from-file` from Phase 6 — DRY). Plus a
  `kustomization.yaml` (one-shot `apply -k`), `secret.example.yaml` (template only, D4), and
  `deploy/k8s/README.md` (run/verify/teardown).
- **Verified live on a multi-node kind cluster (1 control-plane + 2 workers, v1.35.0):** all pods
  Ready; migrate Job Complete (schema at `0004`); `SELECT 1` through pgbouncer (scram-sha-256); api
  `/health` `db:ok`; **worker drained an enqueued briefing job** (queued→done, Briefing row written);
  frontend serves HTML with the ingress API host baked into the client bundle; ingress smoke `/health`
  200 + UI 200 (via `Host` header); **HPA scaled api 1→4 under `hey` load** (CPU peaked 400%/50%,
  36,293 reqs all 200, pods spread across both workers) **and back 4→1**; Prometheus scrapes the api
  (`up{job=second-brain-api}=1`); Grafana `/api/health` 200. `kubectl apply -k` server-dry-run clean.
- **CI/CD:** new **`.github/workflows/k8s.yml`** (kind-action, pinned kind v0.31.0/node v1.35.0,
  ingress-nginx v1.12.3, metrics-server v0.7.2): build+load images → create secret/configmaps →
  apply → wait all rollouts → smoke `/health` + UI through ingress → kind-action tears the cluster
  down. The eval-gated **`ci.yml` is untouched** (D8). HPA load stays a local evidence step (D13).
- **Decisions (D1–D13, ADR-0014):** multi-node kind; local images via `kind load` + `IfNotPresent`
  (no registry, $0); StatefulSet+migrate-Job; ConfigMap/Secret split (secrets uncommitted); host
  ingress; HPA-on-CPU; reuse monitoring; new K8s CI; **managed cloud OFF by default (D9)**; teardown
  (D10). Added: D11 NEXT_PUBLIC build-time bake, D12 pgbouncer env-config, D13 local HPA evidence.
- **Off-spec fix:** added a root **`.dockerignore`** — without it the repo-root build context shipped
  the host `backend/.venv` (1.3G) and `frontend/node_modules` (660M, wrong-OS) INTO the images,
  bloating the backend and breaking the frontend. The Phase-6 images were only `docker compose
  config`-linted, never built, so this latent bug surfaced on first real build. Detail in
  `implementation-notes.md`.
- **Teardown (D10):** `kind delete cluster` — 3 nodes deleted, `No kind clusters found`, no
  `second-brain` containers. **Nothing left running ($0).** No managed cloud was ever created.
- **PR:** [#11](https://github.com/tomnguyen103/second-brain/pull/11) — `phase-7-impl` → main; merge
  gated on CI (the new `k8s.yml` + the untouched eval-gated `ci.yml`) green **and** the CodeRabbit
  (Pro) deep review addressed.
- **Next:** roadmap phases 0–7 all complete. Optional follow-ups: provision the Oracle box + execute
  the deploy runbook; CPU-only torch image; the optional managed-cluster (GKE/EKS) capstone (D9, paid
  — would need explicit go-ahead and immediate teardown).

### 2026-06-02 — Phase 5 COMPLETE: daily briefing + scheduled pipelines (durable worker)
- **Branch:** `phase-5-impl` (off main, Phase 6 merged via PR #9). Plan in `docs/phase-5-plan.md`;
  decisions in ADR-0013. Phase 5 was skipped on the 4 → 6 jump; this picks up the deferred items
  and the roadmap's scheduled-summarization feature. TDD throughout (red → green → commit).
- **What shipped:** the **durable job worker** finally exercising ADR-0004's `jobs` table —
  `app/jobs/queue.py` (enqueue / `claim_next` with `FOR UPDATE SKIP LOCKED` / mark_done /
  mark_failed-with-retry), `app/jobs/worker.py` (`run_once` + resident `--loop`), and a handler
  registry (`app/jobs/handlers.py`). A **briefing** service (`app/briefing/service.py`) that
  summarizes documents ingested since the last briefing's `period_end` (else a 24h lookback) via
  the `LLMClient`, composes markdown, and persists a **`Briefing`** (migration **`0004`**).
  `GET /briefing` (latest) + `GET /briefing/history`. **Async `research_topic`** now runs through
  the same worker (`research` job) — closes the ADR-0010 Phase-4 deferral. Tiny enqueue CLI
  (`app/jobs/enqueue.py`) for OS cron.
- **Decisions (D1–D7, ADR-0013):** poll-based worker (NOTIFY deferred); **OS cron** scheduler
  (no APScheduler/pg_cron); **store-and-display** delivery (no email/secret in v1);
  briefing scope = docs-since-last-briefing; new `briefings` table; async research via the worker;
  `fake` LLM for deterministic tests. Empty window → "nothing new" briefing, **no LLM call**
  (idempotent re-enqueue).
- **Verified:** backend `pytest` **146 passed** (was 118; +28 across config/queue/worker/briefing-
  format/build_briefing/handlers/API). Live `--once` smoke: `enqueue briefing` → `worker --once`
  → stored Briefing (12 docs in the 24h window, markdown body); second run on the empty queue →
  "no eligible job". Prod compose validates with the new `worker` service (`docker compose config`
  OK). DB: migration `0004_briefings` applied live (`alembic upgrade head`).
- **Deploy wiring:** `worker` service in `deploy/docker-compose.prod.yml`
  (`python -m app.jobs.worker --loop`, same env/DSN as api via PgBouncer); cron snippet in
  `docs/runbooks/deploy-checklist.md` §7 enqueues the daily briefing.
- **Deferred (per ADR-0013):** `LISTEN/NOTIFY` wake-up (latency optimization); RSS/GitHub
  connector sources; email/SMTP delivery; a savepoint-wrapped reaper for poisoned-session jobs.
- **Next:** Phase 7 — Kubernetes learning track on local k3s/kind, or provision the Oracle box
  and execute the deploy runbook.

### 2026-06-02 — Phase 6 COMPLETE: productionize + data-ops hardening (code/config; live deploy = runbook)
- **Branch:** `phase-6-impl` (off main). Plan in `docs/phase-6-plan.md`; decisions in ADR-0011
  (VPS) + ADR-0012 (productionization + governance). Live VPS deploy is deferred to a runbook
  (the box isn't bought yet) — everything here builds and tests without a server, like prior
  phases' deferrals.
- **VPS decided (ADR-0011):** **Oracle Cloud Always Free (Singapore)** primary ($0, 24 GB, low
  SEA latency), **Contabo SG ~$5/mo (8 GB)** paid fallback. Low cost was the priority; RAM is the
  binding constraint (torch embedder + monitoring stack), LLM is offloaded so no GPU. Closes the
  parking-lot item.
- **What shipped (data governance):** app-layer **audit** service (`app/dataops/audit.py`);
  **retention** TTL nulling `documents.raw_text` after embedding (`retention.py`); **GDPR**
  source-level **export + delete-my-data** with FK cascade (`erasure.py`); admin-token-guarded
  endpoints (`/data/export`, `DELETE /data/sources/{id}`, `/admin/retention/purge`); migration
  **`0003`** enabling **RLS** + permissive policies on the 8 user-data tables (owner-bypass, no
  FORCE — suite stays green).
- **Observability:** Prometheus **`/metrics`** (request count + latency histogram, labelled by
  route template) via `app/obs/metrics.py` + middleware; `deploy/` prod stack adds Prometheus
  (scrape + alert rules) and provisioned Grafana (datasource + dashboard), plus PgBouncer
  (session pooling) and Redis.
- **CI/CD:** `.github/workflows/ci.yml` — unit → integration (vs `pgvector/pgvector:pg16`
  service) → **eval quality gate** (`app/eval/gate.py`, fake LLM) that fails the build on a
  retrieval/citation regression.
- **Query tuning:** `docs/query-optimization.md` — measured EXPLAIN ANALYZE before/after: HNSW
  **0.088 ms vs 0.706 ms** exact (~8×, ~2k rows); GIN bitmap **0.436 ms vs 2.340 ms** seqscan
  (~5.4×, ~30k rows). Measured inside a rolled-back txn (no dev-DB pollution).
- **Ops docs:** `docs/runbooks/{deploy-checklist,backup-restore,incident-response}.md`.
- **Verified:** backend `pytest` **118 passed** (was 79; +39 across config/audit/retention/
  erasure/dataops-API/metrics/RLS/eval-gate). Eval gate run: hit@k=1.000, citation=1.000,
  refusal=0.923 → PASSED. Prod compose validated with `docker compose config`. RLS confirmed
  (`relrowsecurity` true on all 8 tables) without breaking owner access.
- **PR #9 → merged to main.** CI all green (unit + integration vs pgvector + eval gate, on both
  push and PR runs). **CodeRabbit:** deep review skipped (free-tier rate limit — 0 inline
  comments / no code issues across two pushes + an explicit re-request); its one advisory
  (docstring coverage) was handled by docstringing production code + a `.coderabbit.yaml` that
  keeps the check an advisory `warning` (test functions deliberately not counted). Detail in
  `implementation-notes.md`.
- **Deferred (per ADR-0012):** live VPS deploy (runbook); transaction-mode pooling; remote
  MLflow; LLM-as-judge eval; Next standalone-output image optimization.
- **Next:** Phase 7 — Kubernetes learning track on local k3s/kind (manifests + HPA + ingress +
  CI/CD), then torn down. Or provision the Oracle box and execute the deploy runbook.

### 2026-06-02 — Phase 4 COMPLETE: MCP server + agentic actions (incl. self-research)
- **Branch:** `phase-4-impl` (off main, Phase 3 merged via PR #7). Plan in `docs/phase-4-plan.md`;
  decision in ADR-0010.
- **What shipped:** an **MCP server** (`app/mcp_server.py`, FastMCP/stdio, `python -m app.mcp_server`)
  exposing five tools — `search_notes` (hybrid retrieval), `create_task`/`list_tasks` (new `tasks`
  table, migration `0002`), `send_digest` (markdown digest of recent activity), and the flagship
  `research_topic` (LLM writes a note → stored as a `research_note` source → auto-ingested → searchable).
  Logic lives in tested services (`app/{tasks,digest,research}`); tools are thin session-opening wrappers.
- **Verified:** backend `pytest` **78 passed** (unit + integration vs live DB on 5433, fake LLM). Live
  smoke: `search_notes("HNSW index tuning")` → top hit "HNSW index tuning"; `send_digest()` → digest with
  counts. MCP `list_tools()` returns the five tools.
- **DB:** migration `0002_tasks` applied live (`alembic upgrade head`). `tasks` table added.
- **Deferred (per ADR-0010):** async research via the `jobs` queue + optional web search (Phase 5);
  digest *delivery* / email transport (Phase 5/6); SSE transport (stdio is the local-client path).
- **Next:** Phase 5 — daily briefing + scheduled pipelines (the `jobs` table + `briefing`/`research` job
  types are already in the schema).

### 2026-06-02 — Phase 3 COMPLETE: evaluation + MLOps (eval set, MLflow, A/B, prompt versioning)
- **Branch:** `phase-3-impl` (off main, which now has Phase 2 merged via PR #6). Planned in
  `docs/phase-3-plan.md`; decisions in ADR-0008 (eval methodology + MLflow) and ADR-0009 (prompt
  versioning + A/B + rollback).
- **What shipped (`backend/app/eval/` + `backend/eval/`):** a fixed eval set (6-topic markdown
  corpus + 13-case `dataset.yaml`, incl. a multi-source case and one off-corpus refusal); a pure
  metrics module (retrieval hit@k/recall@k/MRR, citation validity, keyword recall, refusal
  correctness, latency p50/p95); a **read-only** eval pipeline + harness (reuses `hybrid_search` +
  versioned `build_messages` + `LLMClient`, persists nothing); MLflow logging to a **local file
  store** (`file:./mlruns`, no server, $0); a runner CLI (`python -m app.eval.runner --configs …`)
  that ingests the corpus, runs each config, logs an MLflow run, and prints an A/B table.
- **Prompt versioning + rollback (ADR-0009):** `app/chat/prompt.py` now has a `PromptSpec` registry
  (`rag-v1` kept byte-for-byte, `rag-v2` variant); `build_messages`/chat select
  `settings.prompt_version`; rollback = set `SECOND_BRAIN_PROMPT_VERSION` back. A/B configs:
  `baseline`/`variant` (deterministic, fake) and `gemini`/`gemini-v2` (real prompt A/B).
- **Verified:** backend `pytest` **64 passed** (unit + integration vs live DB on 5433). Live A/B
  run (`baseline,variant`, real MiniLM embedder + fake LLM) logged 2 MLflow runs and printed the
  table: **hit@k = recall@k = 1.000, MRR ≈ 0.917, citation_validity = 1.000, refusal_accuracy =
  0.923**. `keyword_recall`/`latency` are ~0 on the fake driver by design (D2/ADR-0008) — the real
  numbers come from the documented `gemini` run.
- **Verification caught + fixed:** the eval runner writes the corpus into the shared dev/test DB,
  which broke `test_retrieval` (its "HNSW tuning" query also matched the new eval HNSW note). Fixed
  by scoping the retrieval tests to their own `source_ids` — the right isolation pattern for a
  shared DB. Detail in `implementation-notes.md`.
- **Deferred (per ADR-0008):** LLM-as-judge grading; richer/larger corpus; remote MLflow server
  (Phase 6). **Note:** the runner seeds an "Eval Corpus" source into the dev DB (idempotent; like
  the Phase 2 smoke seed) and writes `./mlruns` (gitignored).
- **Next:** Phase 4 — MCP server + agentic actions (create task, send digest, search, research-this-topic).

### 2026-06-02 — Phase 2 COMPLETE: verified end-to-end + history-citation fix
- **Branch:** `phase-2-impl`. Verified Phase 2 against its Definition of Done before flipping
  status to ✅ — ran the commands, didn't trust the prior log.
- **Static gates (all green):** backend `pytest` **37 passed** (was 36; +1 new test); frontend
  `tsc --noEmit` exit 0; `next build` exit 0 (`/chat` + `/search` static).
- **Live E2E (real DB on 5433, `fake` LLM for determinism):** ingest→`/search` (5 ranked hybrid
  hits)→`/chat` (answer with clickable `[1][2]` → CitationCard showing title/source/snippet/method/
  score)→`/feedback` (201). Conversation sidebar loads live `/conversations`; dark mode works.
- **Gap found & fixed during verification:** replaying a past conversation from the sidebar
  rendered **dead, non-clickable `[n]` markers** and dropped the feedback/source/latency footer —
  because `GET /conversations/{id}` returned raw `retrievals` (chunk_id/rank/score) but not
  reconstructed `citations`, and the chat page mapped history to `{role, content}` only. Fixed:
  the detail endpoint now reconstructs `citations` (marker→document/source/snippet, mirroring
  `chat.service`'s marker logic via `parse_citations` + `load_display_chunks`); the chat page
  rehydrates the live-chat shape so replayed turns get clickable citations + working thumbs.
  Verified live: conversation #34 replay shows 2 clickable cards + feedback "Saved". Detail in
  `implementation-notes.md`.
- **Files:** `backend/app/api/conversations.py`, `backend/app/schemas/conversations.py`,
  `backend/tests/integration/test_search.py` (new test), `frontend/app/chat/page.tsx`,
  `frontend/lib/api/types.ts`. (Plus the prior uncommitted `ConversationSidebar.tsx` dark-mode fix.)
- **Deferred (not blockers, per DoD):** SSE streaming; `npm run gen-types` (hand-written
  `types.ts` intentionally diverges from openapi-typescript's `paths`/`components` shape — running
  codegen would break current imports); feedback analytics (Phase 3/6); auth/deploy (Phase 6).
- **Note:** live smoke seeded the dev DB with a `Phase2 Verify Seed` source + conversations
  #34/#35 + feedback rows (harmless on dev; not committed).
- **Next:** Phase 3 — Evaluation + MLOps (eval set, MLflow harness, A/B, prompt versioning + rollback).

### 2026-06-01 — Phase 2 IN PROGRESS: backend deltas + Next.js UI scaffold
- **Branch:** `phase-2-impl` (off main, which now has Phase 1 merged).
- **Backend deltas shipped:** `GET /search` (hybrid_search wrapper), `GET /conversations`,
  `GET /conversations/{id}`, `POST /feedback` — all with Pydantic v2 schemas + integration tests.
- **Frontend scaffold shipped:** Next.js 16 + TypeScript + Tailwind v4 + shadcn/ui + TanStack Query.
  Routes: `/chat` (message → cited answer → [n] → CitationCard popover; SourceFilter; conversation
  history load), `/search` (full-text+vector results with source/tag filters). Conversation sidebar
  with 15s auto-refresh. Private-mode toggle. Feedback thumbs per message.
- **Build status:** `tsc --noEmit` clean; `next build` clean (both routes static-generate).
- **Open decisions resolved:** non-streaming first; openapi-typescript codegen script added
  (`npm run gen-types`); TanStack Query; Tailwind + shadcn/ui; hosting deferred to Phase 6.
- **Not yet done:** E2E smoke against live backend (requires `docker compose up -d` + backend
  running); `npm run gen-types` to sync types from live `/openapi.json`; streaming (deferred).
- **Next:** run backend + frontend together, take the MVP screenshot, then decide on Phase 2 polish
  (streaming SSE, Vitest component tests) vs moving to Phase 3.

### 2026-06-01 — Phase 1 COMPLETE: RAG MVP shipped (POST /ingest + POST /chat)
- **Branch:** `phase-1-impl` (28 tests, 0 failures). Merge to main when ready.
- **What shipped:** Python 3.12 venv (uv); `LLMClient` seam (Gemini/Ollama/fake); local
  MiniLM-384 embeddings (`sentence-transformers`); content hashing + semantic chunking
  (ADR-0003); hybrid pgvector + full-text retrieval fused with RRF (ADR-0005); cited
  answers (ADR-0006); inline ingest (source→dedupe→chunk→embed→store); chat service
  (retrieve→prompt→generate→persist conversations/messages/retrievals); FastAPI app with
  `/health`, `/ingest`, `/chat` routers + Pydantic v2 schemas (ADR-0007).
- **Off-spec fixes recorded in `implementation-notes.md`:** `tsv` column marked `Computed`
  in ORM (was causing INSERT errors on GENERATED ALWAYS column); chunking overlap falls
  back to word-level when unit-level step-back can't reach the overlap budget; psycopg3
  NULL array params need explicit `bindparam` types (`ARRAY(BigInteger/Text)`);
  `test_defaults` now uses `monkeypatch.delenv` to isolate from CI shell env vars.
- **Verified:** `pytest -v` → 28 passed (16 unit + 12 integration) against live pgvector DB.
- **Next:** Phase 2 — Next.js chat UI (streaming, citations, semantic search). DB-bound
  integration tests (Tasks 2, 9–12) require `SECOND_BRAIN_TEST_DATABASE_URL` set.

### 2026-06-01 — Docker installed; Phase 0 migration applied live (DB on host port 5433)
- **Docker Desktop** installed (Win 11, WSL2 backend, engine v29.5.2); `docker compose up -d`
  brings up `pgvector/pgvector:pg16` (container `second_brain_db`, healthy).
- **Phase 0 migration applied for real** (first time — was offline-only before): `alembic
  upgrade head` → `0001_baseline (head)`. Verified live: 13 relations (12 tables +
  `alembic_version`), `vector` 0.8.2 extension, `ix_embeddings_hnsw` HNSW index.
- **Port moved to 5433:** a native PostgreSQL 16 service owns host 5432, so the Docker DB now
  publishes on **5433** (container 5432). `docker-compose.yml` + `app/config.py` default updated;
  stale `backend/.env` removed. `backend/.env.example` still says 5433 (harness-protected) —
  update to 5433 manually. Detail in `implementation-notes.md`.
- **Next:** Phase 1 implementation per `docs/phase-1-plan.md` — DB-bound tasks (2, 9–12) now unblocked.

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
- ~~Which VPS provider to buy~~ — RESOLVED 2026-06-02 in ADR-0011: **Oracle Cloud Always Free
  (Singapore)** primary ($0, 24 GB, low SEA latency), **Contabo SG ~$5/mo (8 GB)** paid fallback.
  Low cost was the priority; refreshed 2026 pricing (Hetzner is EU/US-only → latency cost for a
  Vietnam daily-use UI).
- ~~Chunking strategy specifics (size/overlap)~~ — RESOLVED in ADR-0003 (~512 tok / ~15% overlap, semantic boundaries).
- ~~**Install Docker Desktop** before Phase 1 end-to-end / integration tests~~ — DONE 2026-06-01: installed, Phase 0 migration applied live; Docker DB on host **5433** (native PG holds 5432).
- ~~Whether to do the optional managed-cluster (GKE/EKS) capstone in Phase 7~~ — DECIDED 2026-06-02
  in ADR-0014 (D9): **OFF by default** (paid; would blow the $0/learning-track constraint). The local
  kind track is the Phase 7 deliverable; a managed-cluster demo stays optional and, if ever run, needs
  explicit go-ahead and immediate teardown.
