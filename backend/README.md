# Second Brain — backend (Phase 1: RAG MVP)

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
