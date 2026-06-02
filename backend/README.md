# Second Brain — backend (through Phase 6: RAG MVP + eval/MLOps + MCP + data-ops/observability)

Phase 1 ships `POST /ingest` and `POST /chat` on the Phase 0 schema: local MiniLM-384
embeddings, hybrid pgvector + full-text retrieval fused with RRF, and cited answers via an
`LLMClient` (Gemini default / Ollama / fake). Phase 0 delivered the Postgres data model.

## Layout

```
backend/
  app/
    config.py          # settings (DB URL via SECOND_BRAIN_DATABASE_URL)
    db/
      base.py          # SQLAlchemy DeclarativeBase
      models.py        # ORM models mirroring the baseline migration
  migrations/
    env.py             # Alembic env (URL from app settings, autogenerate target = Base.metadata)
    versions/
      0001_baseline.py # hand-written baseline: all tables + pgvector/full-text indexes
  alembic.ini
  requirements.txt
```

Design docs: [`../docs/data-model/er-diagram.md`](../docs/data-model/er-diagram.md) and
[`../docs/adr/`](../docs/adr/) (ADR-0002 embeddings, 0003 chunking, 0004 job queue).

## Phase 1 — run & verify

```powershell
# 0) DB-free: unit tests (no Docker needed)
cd backend
.\.venv\Scripts\Activate.ps1
pytest tests/unit -v

# 1) Bring up Postgres + pgvector and migrate (already applied — skip if current)
docker compose up -d db          # from repo root
alembic upgrade head

# 2) Full suite (unit + integration) against the real DB
$env:SECOND_BRAIN_TEST_DATABASE_URL = "postgresql+psycopg://second_brain:second_brain@localhost:5433/second_brain"
$env:SECOND_BRAIN_LLM_PROVIDER = "fake"
pytest -v                        # 28 tests, all pass

# 3) Run the API (fake LLM — no key needed for smoke)
uvicorn app.main:app --reload
#   POST /ingest a couple of notes, then POST /chat — see /docs for the schema
#   For real answers: set SECOND_BRAIN_GEMINI_API_KEY and drop the SECOND_BRAIN_LLM_PROVIDER override
```

## Phase 3 — evaluation + MLOps (run & verify)

Measure answer quality and compare configs. The eval set lives in `backend/eval/`
(corpus + `dataset.yaml`); metrics, harness, MLflow logging, and the A/B runner are in
`app/eval/`. See ADR-0008 (methodology + MLflow) and ADR-0009 (prompt versioning + rollback).

```powershell
cd backend; .\.venv\Scripts\Activate.ps1

# 0) Eval tests — all DB-free except the harness (which needs the DB)
pytest tests/unit/test_eval_metrics.py tests/unit/test_eval_dataset.py `
       tests/unit/test_eval_configs.py tests/unit/test_eval_runner.py `
       tests/unit/test_prompt_versions.py tests/unit/test_eval_mlflow.py -v
$env:SECOND_BRAIN_TEST_DATABASE_URL = "postgresql+psycopg://second_brain:second_brain@localhost:5433/second_brain"
pytest tests/integration/test_eval_harness.py -v

# 1) Deterministic A/B (fake LLM — reproducible, no key). Ingests the corpus, logs 2 MLflow runs.
python -m app.eval.runner --configs baseline,variant

# 2) Real prompt A/B (rag-v1 vs rag-v2) — needs a Gemini key; this is the shareable comparison
$env:SECOND_BRAIN_GEMINI_API_KEY = "..."
python -m app.eval.runner --configs gemini,gemini-v2

# 3) Open the MLflow comparison UI (reads the local file store; no server/bill)
mlflow ui --backend-store-uri ./mlruns      # then browse http://localhost:5000

# Prompt rollback: just point the active version back and restart — no code change, no deploy
$env:SECOND_BRAIN_PROMPT_VERSION = "rag-v1"
```

> Notes: the deterministic run reports `keyword_recall = 0` and `latency ≈ 0` by design (the
> `fake` driver returns a canned, instant answer) — the `gemini` run produces the meaningful
> answer-quality numbers. The runner writes the eval corpus into the dev DB (idempotent — content
> -hash dedupe) and the MLflow store to `./mlruns` (gitignored).

## Phase 4 — MCP server + agentic actions (run & verify)

Exposes the brain's actions as MCP tools: `search_notes`, `create_task`, `list_tasks`,
`send_digest`, `research_topic`. Services in `app/{tasks,digest,research}`; server in
`app/mcp_server.py`. See ADR-0010.

```powershell
cd backend; .\.venv\Scripts\Activate.ps1

# 0) Apply migration 0002 (tasks table), then run the Phase 4 tests
docker compose up -d db          # from repo root, if not already up
alembic upgrade head             # -> 0002_tasks
$env:SECOND_BRAIN_TEST_DATABASE_URL = "postgresql+psycopg://second_brain:second_brain@localhost:5433/second_brain"
pytest tests/unit/test_mcp_server.py tests/unit/test_research_prompt.py `
       tests/unit/test_digest_format.py tests/integration/test_tasks.py `
       tests/integration/test_research.py tests/integration/test_digest.py -v

# 1) Run the MCP server over stdio (fake LLM = keyless; drop it + set a Gemini key for real research)
$env:SECOND_BRAIN_LLM_PROVIDER = "fake"
python -m app.mcp_server

# 2) Or explore it interactively with the MCP Inspector
mcp dev app/mcp_server.py        # opens the Inspector; call search_notes / create_task / research_topic

# 3) Connect from Claude Desktop — add to its MCP config (claude_desktop_config.json):
#   "second-brain": { "command": "<abs path>/.venv/Scripts/python.exe", "args": ["-m","app.mcp_server"],
#                     "cwd": "<abs path>/backend" }
```

> Notes: `research_topic` with the `fake` driver stores a deterministic note (still embedded +
> searchable); set `SECOND_BRAIN_GEMINI_API_KEY` + drop the `fake` override for real research.
> `create_task`/`research_topic` write to the configured DB.

## Phase 6 — productionization + data-ops (run & verify)

Data governance (RLS, audit, retention, GDPR export/delete), Prometheus metrics, an eval-gated
CI pipeline, and the prod Compose stack. Services in `app/dataops/*` + `app/obs/*`; admin API in
`app/api/dataops.py`; the prod stack + monitoring config in `deploy/`. See ADR-0011 (VPS) and
ADR-0012 (productionization + governance).

```powershell
cd backend; .\.venv\Scripts\Activate.ps1

# 0) Apply migration 0003 (RLS), then run the Phase 6 tests
docker compose up -d db          # from repo root, if not already up
alembic upgrade head             # -> 0003_rls_audit
$env:SECOND_BRAIN_TEST_DATABASE_URL = "postgresql+psycopg://second_brain:second_brain@localhost:5433/second_brain"
pytest tests/unit/test_config_phase6.py tests/unit/test_metrics.py tests/unit/test_eval_gate.py `
       tests/integration/test_audit.py tests/integration/test_retention.py `
       tests/integration/test_erasure.py tests/integration/test_dataops_api.py `
       tests/integration/test_rls.py -v

# 1) Metrics: run the API and scrape /metrics
uvicorn app.main:app --reload    # then: curl http://localhost:8000/metrics

# 2) Admin / data-subject endpoints (set a token to enable them; blank => 503)
$env:SECOND_BRAIN_ADMIN_TOKEN = "a-long-random-token"
#   GET    /data/export?source_id=<id>        (GDPR access)   -> Authorization: Bearer <token>
#   DELETE /data/sources/<id>                 (GDPR erasure)
#   POST   /admin/retention/purge?older_than_days=180   (null old raw_text)

# 3) Eval gate (the CI quality gate; exit 0 = quality OK)
python -m app.eval.gate

# 4) Validate the production stack parses (does NOT start it)
docker compose -f ../deploy/docker-compose.prod.yml --env-file ../deploy/.env.prod.example config | Out-Null
```

> Deploy is a runbook, not run here — see [`../docs/runbooks/deploy-checklist.md`](../docs/runbooks/deploy-checklist.md),
> `backup-restore.md`, and `incident-response.md`. Query-tuning before/after numbers are in
> [`../docs/query-optimization.md`](../docs/query-optimization.md). CI is `.github/workflows/ci.yml`
> (unit → integration vs pgvector → eval gate).

## Phase 0 — run & verify (from repo root)

```bash
# 1. Start Postgres + pgvector
docker compose up -d db

# 2. Install deps and apply migrations
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows; use bin/activate on *nix
pip install -r requirements.txt
# .env is optional: config.py already defaults to the Docker DB on host port 5433.
# Only create one to override defaults — and if you copy the example, change :5432 → :5433
# first, since .env.example still pins 5432 (which clashes with a native Postgres on that port).
alembic upgrade head

# 3. Verify objects exist
docker exec -it second_brain_db psql -U second_brain -d second_brain -c "\dt"
docker exec -it second_brain_db psql -U second_brain -d second_brain \
  -c "SELECT extname FROM pg_extension WHERE extname='vector';"
docker exec -it second_brain_db psql -U second_brain -d second_brain \
  -c "\d+ chunks"     # confirms generated tsv column + GIN index
docker exec -it second_brain_db psql -U second_brain -d second_brain \
  -c "SELECT indexname FROM pg_indexes WHERE tablename='embeddings';"  # HNSW index
```

Roll back the baseline with `alembic downgrade base`.

## Notes
- `0001_baseline.py` is the **source of truth** for DDL (pgvector extension, `GENERATED`
  tsvector column, HNSW/GIN indexes). `models.py` mirrors it for app use and future
  `alembic revision --autogenerate`. Keep them in sync.
- HNSW (not IVFFlat) is the vector index — see ADR-0002.
