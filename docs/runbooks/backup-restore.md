# Runbook — Backup & restore (Postgres)

The database is the only stateful component that matters (embeddings can be recomputed from
`raw_text` only while it is retained — after retention purge, the chunks/embeddings ARE the
data, so back them up). Redis is a cache (disposable). MLflow `./mlruns` is regenerable.

## What to back up
- **Postgres** `second_brain` database — the source of truth (sources, documents, chunks,
  embeddings, conversations, audit_log, tasks).
- `deploy/.env.prod` and `deploy/pgbouncer/userlist.txt` — store these in a password manager,
  NOT in the DB backup and NOT in git.

## Nightly logical backup (cron)
```bash
# /etc/cron.daily/second-brain-backup  (chmod +x)
set -euo pipefail
cd /home/USER/second-brain
ts=$(date +%Y%m%d-%H%M%S)
docker compose -f deploy/docker-compose.prod.yml exec -T db \
  pg_dump -U second_brain -d second_brain -Fc \
  > /var/backups/second-brain/sb-$ts.dump
# keep 14 days
find /var/backups/second-brain -name 'sb-*.dump' -mtime +14 -delete
```
`-Fc` is the custom format (compressed, supports selective restore). Verify a fresh dump is
non-empty (`ls -la`) and periodically test-restore it (below) — an untested backup is a guess.

## Restore (full)
```bash
# into a clean database (DANGER: drops existing objects)
docker compose -f deploy/docker-compose.prod.yml up -d db
cat sb-YYYYMMDD-HHMMSS.dump | docker compose -f deploy/docker-compose.prod.yml exec -T db \
  pg_restore -U second_brain -d second_brain --clean --if-exists --no-owner
# pgvector extension + RLS policies come from the dump; confirm:
docker compose -f deploy/docker-compose.prod.yml exec db \
  psql -U second_brain -d second_brain -c "SELECT count(*) FROM embeddings;"
```

## Restore-test (do this monthly)
Restore the latest dump into a throwaway database and run a sanity query — proves the backup is
actually recoverable:
```bash
docker compose -f deploy/docker-compose.prod.yml exec db createdb -U second_brain sb_restore_test
cat sb-latest.dump | docker compose ... exec -T db pg_restore -U second_brain -d sb_restore_test --no-owner
docker compose ... exec db psql -U second_brain -d sb_restore_test -c "\dt"
docker compose ... exec db dropdb -U second_brain sb_restore_test
```

## Before a migration release
Always snapshot first, so a bad migration is recoverable:
```bash
docker compose ... exec -T db pg_dump -U second_brain -d second_brain -Fc > pre-migrate-$(date +%s).dump
# deploy; if the migration misbehaves: alembic downgrade -1  (or restore the dump)
```

## Off-box copy
Sync `/var/backups/second-brain` to object storage or another host (rclone/scp) — a backup that
only lives on the same VPS doesn't survive losing the VPS.
