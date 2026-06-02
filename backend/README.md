# Second Brain — backend (Phase 0: data layer)

Phase 0 delivers the Postgres data model and Alembic migrations only. FastAPI app, ingest
worker, and `LLMClient` arrive in Phase 1.

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

## Run & verify (from repo root)

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
