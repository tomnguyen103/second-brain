# Runbook — Backup & restore (Postgres)

The database is the only stateful component that matters (embeddings can be recomputed from
`raw_text` only while it is retained — after retention purge, the chunks/embeddings ARE the
data, so back them up). Redis is a cache (disposable). MLflow `./mlruns` is regenerable.

## What to back up
- **Postgres** `second_brain` database — the source of truth (sources, documents, chunks,
  embeddings, conversations, audit_log, tasks).
- `deploy/.env.prod` — store it in a password manager, NOT in the DB backup and NOT in git.

## Nightly logical backup (cron)
Use the checked-in template at `deploy/cron/second-brain-backup`. It writes compressed custom
format dumps to `/var/backups/second-brain`, writes a `.sha256` checksum next to each dump, and
deletes dumps older than 14 days by default.

```bash
# one-time install on the VPS
cd /root/second-brain
sudo install -m 0750 deploy/cron/second-brain-backup /usr/local/sbin/second-brain-backup
sudo mkdir -p /var/backups/second-brain
sudo chmod 700 /var/backups/second-brain
echo '17 2 * * * root /usr/local/sbin/second-brain-backup >> /var/log/second-brain-backup.log 2>&1' | sudo tee /etc/cron.d/second-brain-backup
```

Smoke the backup immediately:

```bash
sudo /usr/local/sbin/second-brain-backup
sudo ls -lh /var/backups/second-brain
sudo sha256sum -c "$(sudo ls -1t /var/backups/second-brain/sb-*.dump.sha256 | head -n 1)"
sudo tail -n 50 /var/log/second-brain-backup.log
```

`-Fc` is the custom format (compressed, supports selective restore). Verify a fresh dump is
non-empty and periodically test-restore it (below) — an untested backup is a guess.

## Restore (full)
```bash
# into a clean database (DANGER: drops existing objects)
DC="docker compose -p second-brain -f deploy/docker-compose.prod.yml -f deploy/docker-compose.vps.yml --env-file deploy/.env.prod"

$DC up -d db
cat sb-YYYYMMDD-HHMMSS.dump | $DC exec -T db \
  pg_restore -U second_brain -d second_brain --clean --if-exists --no-owner
# pgvector extension + RLS policies come from the dump; confirm:
$DC exec db \
  psql -U second_brain -d second_brain -c "SELECT count(*) FROM embeddings;"
```

## Restore drill (do this monthly)
Restore the latest dump into a throwaway database and run sanity queries. This proves the backup
is actually recoverable without overwriting production data:

```bash
DC="docker compose -p second-brain -f deploy/docker-compose.prod.yml -f deploy/docker-compose.vps.yml --env-file deploy/.env.prod"
latest="$(ls -1t /var/backups/second-brain/sb-*.dump | head -n 1)"
test_db="sb_restore_drill_$(date +%Y%m%d)"

sha256sum -c "$latest.sha256"
$DC exec -T db dropdb -U second_brain --if-exists "$test_db"
$DC exec -T db createdb -U second_brain "$test_db"
cat "$latest" | $DC exec -T db pg_restore -U second_brain -d "$test_db" --no-owner
$DC exec -T db psql -U second_brain -d "$test_db" -c "\dt"
$DC exec -T db psql -U second_brain -d "$test_db" -c "SELECT count(*) AS documents FROM documents; SELECT count(*) AS embeddings FROM embeddings; SELECT count(*) AS conversations FROM conversations;"
$DC exec -T db dropdb -U second_brain "$test_db"
```

Record the drill date and result in `docs/PROGRESS.md` if it found or fixed anything.

## Before a migration release
Always snapshot first, so a bad migration is recoverable:
```bash
DC="docker compose -p second-brain -f deploy/docker-compose.prod.yml -f deploy/docker-compose.vps.yml --env-file deploy/.env.prod"

$DC exec -T db pg_dump -U second_brain -d second_brain -Fc > pre-migrate-$(date +%s).dump
# deploy; if the migration misbehaves: alembic downgrade -1  (or restore the dump)
```

## Off-box copy
A backup that only lives on the same VPS does not survive losing the VPS. The no-new-cost default
is to periodically copy `/var/backups/second-brain` to a trusted local machine over `scp` or
`rsync`, and to keep `deploy/.env.prod` in a password manager. Paid object storage is also
reasonable, but it adds recurring cost and needs explicit
approval before using it for this project.
