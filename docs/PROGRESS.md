# Progress Log — Second Brain

Running log of what's done, in progress, and next. Keep this current at the end of each
session — the master prompt treats it as the source of truth for "where we are."

## Status at a glance

| Phase | Description | Status |
|---|---|---|
| Planning | Project design, stack, cost model, roadmap | ✅ Complete |
| 0 | Data model + ER diagram + Alembic migrations + pgvector/full-text indexes | ✅ Complete |
| 1 | RAG MVP: FastAPI /ingest + /chat, hybrid retrieval, Gemini via LLMClient | ✅ Complete |
| 2 | Next.js chat UI (citations, semantic search, feedback; streaming deferred) | ✅ Complete |
| 3 | Evaluation + MLOps: eval set, MLflow, A/B, prompt versioning + rollback | ✅ Complete |
| 4 | MCP server + agentic actions incl. self-research tool | ✅ Complete |
| 5 | Daily briefing + scheduled pipelines | ✅ Complete |
| 6 | Productionize on VPS + data-ops hardening | ✅ Complete |
| 7 | Kubernetes learning track on local k3s/kind | ✅ Complete |

Legend: ⬜ not started · 🟡 in progress · ✅ complete

## Session log

Add a dated entry per working session. Most recent on top.

### 2026-06-03 - CodeRabbit security review follow-up
- **What:** addressed CodeRabbit feedback on PR #18. Added locking around the in-memory MCP
  approval registry, hid approved approvals from `list_pending`, made vault full scans avoid stale
  deletion when no paths are successfully indexed, included uppercase `.MD` files, preserved leading
  Markdown whitespace on append, and chained sensitive-ingest HTTP errors.
- **Safety polish:** source delete previews now return a redacted display name plus a non-secret
  `confirm_token`, so operators can confirm destructive deletes without exposing a raw source name
  that might contain private data. Exact `confirm_source_name` remains supported.
- **Verified:** backend `.venv` full suite: `96 passed, 88 skipped`; `python -m compileall app`;
  `git diff --check`.

### 2026-06-03 - Local-first MCP/Obsidian security hardening
- **What:** applied the security review fixes for local-first MCP/Obsidian handling. Restored the
  missing `backend/app/vault/*.py` source, added safe vault path resolution, Markdown/frontmatter
  helpers, approved-note checks, and an in-memory MCP approval gate.
- **Security changes:** MCP write tools now require a pending approval to be approved with
  `SECOND_BRAIN_MCP_WRITE_APPROVAL_TOKEN` before execution; MCP/search/digest/export responses are
  redacted for likely secrets/contact/payment data; `/ingest` refuses sensitive documents and
  requires `notes_folder` Markdown to have `status: approved`; RAG context is marked as untrusted
  note content; retention purge previews by default and rejects unsafe windows; source delete
  requires a delete-preview token or exact source-name confirmation.
- **Export/VPS guardrails:** local Markdown export now requires `--confirm-local-export local-only`,
  redacts sensitive output, honors `SECOND_BRAIN_DATA_ENVIRONMENT`, and production compose sets that
  value to `production`.
- **Verified:** backend `.venv` full suite: `92 passed, 87 skipped` (DB-backed integration tests
  skipped because `SECOND_BRAIN_TEST_DATABASE_URL` was not set).

### 2026-06-03 - Local-first export-and-purge prep, dry-run only
- **What:** added the missing `docs/runbooks/local-first-export-purge.md` with hard rules, current
  local/VPS export options, keeper checklists for research notes, briefings, chat answers, and
  source documents, Markdown export formats, verification steps, and a future purge gate. No purge
  command is part of the prep workflow.
- **Added:** `backend/app/dataops/export_markdown.py`, a local-only Markdown exporter that refuses
  non-local database hosts, reads inside a Postgres read-only transaction, rolls the transaction
  back, and writes review files to a temp/local folder. Added DB-free unit coverage in
  `backend/tests/unit/test_export_markdown.py`.
- **Verified locally:** Docker DB was healthy on `localhost:5433`; dry-run wrote to
  `C:\Users\huuth\AppData\Local\Temp\second-brain-keeper-export-20260603-172207` with
  0 research notes, 1 briefing, 1 positive-feedback chat answer, 16 source-document candidates,
  and 1 manifest. Spot-checked briefing/chat/source Markdown. `audit_log` stayed empty
  (`count = 0`). Unit suite: `76 passed`. No remote/VPS data was touched and nothing was deleted.

### 2026-06-03 - NotebookLM -> Obsidian daily research workflow made repeatable
- **What:** updated the real Obsidian templates in
  `C:\Users\huuth\Documents\SecondBrainVault\Templates` for `Research Brief`,
  `NotebookLM Session`, and `Source Digest`. Each template now has the required frontmatter
  (`title`, `kind`, `status`, `created`, `derived`, `source_tool`, `tags`) plus review,
  approval, reindex, and search-verify sections.
- **Added:** `C:\Users\huuth\Documents\SecondBrainVault\10 Research\Daily Research Prompt.md`,
  `.obsidian/templates.json` pointing Obsidian Templates at the vault `Templates` folder, and the
  missing repo docs `docs/local-first-agentic-research-plan.md`,
  `docs/adr/0015-local-first-obsidian-memory.md`, and
  `docs/notebooklm-to-obsidian-workflow.md`.
- **Workflow clarified:** ask the question, search/decide whether NotebookLM is needed, use
  NotebookLM manually, paste only useful source-aware output, save approved Markdown, reindex
  through `/ingest`, and search verify. NotebookLM remains manual; raw transcripts are not saved
  by default.

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
