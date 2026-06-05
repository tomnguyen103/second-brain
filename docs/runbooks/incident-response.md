# Runbook — Incident response

Single-user app on one box, so "incident response" = a short triage loop. Start with the private
API health and metrics endpoints, then container logs. Prometheus/Grafana configs remain in
`deploy/`, but production Compose does not start monitoring containers until a scanned-clean
runtime is selected.

## Triage order
1. `curl -s localhost:8000/health` → is `db` `ok`?
2. `DC="docker compose -p second-brain -f deploy/docker-compose.prod.yml -f deploy/docker-compose.vps.yml --env-file deploy/.env.prod"` → use this for all stack commands.
3. `$DC ps` → which containers are up/healthy?
4. `$DC logs --tail=200 <service>` → recent errors.
5. `curl -fsS localhost:8000/metrics | head` -> confirm the metrics endpoint is responding.

## Health check commands
Run these on the VPS unless noted:

```bash
DC="docker compose -p second-brain -f deploy/docker-compose.prod.yml -f deploy/docker-compose.vps.yml --env-file deploy/.env.prod"

curl -fsS localhost:8000/health
curl -fsS https://YOUR_VPS_IP.sslip.io/api/health
$DC ps
$DC exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
$DC exec -T redis redis-cli ping
$DC exec -T db sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;"'
sudo ufw status verbose
```

The retained Prometheus/Grafana configs can be reintroduced later with scanned-clean images or
custom builds. Until then, use the API's private `/metrics` endpoint directly.

## Metric signal -> likely cause -> action

### API metrics/health unreachable
- `$DC ps api` / `$DC logs api`. Common: DB not healthy yet, or a bad migration on
  the startup `alembic upgrade head` step.
- DB down → see "DB unreachable". Migration failure → restore pre-migrate dump
  (`backup-restore.md`) or `alembic downgrade -1`, then redeploy a green commit.

### `HighErrorRate` (5xx > 5%)
- `$DC logs api` for tracebacks. If it started after a deploy → roll back to the previous green SHA
  (`deploy-checklist.md` rollback section).
- If Gemini-related (quota/timeout): flip to private mode `SECOND_BRAIN_LLM_PROVIDER=ollama`
  (if Ollama is present) or wait out the quota; chat refuses gracefully on no-context.

### p95 latency > 2s
- Usually the LLM call (Gemini) — check `chat` latency in messages and API logs. Embedding/retrieval
  is sub-ms locally (see `docs/query-optimization.md`).
- DB slow? Check `pg_stat_activity`, SQLAlchemy pool saturation, and whether a schema change missed
  an index → `EXPLAIN ANALYZE` the slow query.

### DB unreachable
- `$DC logs db`. Disk full is the classic cause: `df -h`; prune old WAL/backups,
  Docker images (`docker system prune`). On 4 GB boxes, OOM can kill Postgres — check `dmesg`
  and add swap if needed.

## Bad retrieval / hallucination spike
- Not an outage but a quality regression. Re-run the eval gate against the corpus
  (`python -m app.eval.gate`) and the real A/B (`python -m app.eval.runner --configs gemini`).
- If a prompt change caused it: roll the prompt back instantly — `SECOND_BRAIN_PROMPT_VERSION=rag-v1`
  and restart `api` (no redeploy; ADR-0009).

## Data-subject request (GDPR)
- Export: `GET /data/export?source_id=<id>` with the normal API bearer and
  `X-Second-Brain-Admin-Token`.
- Erase: `DELETE /data/sources/{id}` (cascades; audited). Both require
  `SECOND_BRAIN_API_TOKEN` plus `SECOND_BRAIN_ADMIN_TOKEN`.

## Secret rotation
Rotate secrets from the VPS, never by committing real values. Update the password manager at the
same time as `deploy/.env.prod`.

Generate replacement values:

```bash
openssl rand -base64 48
```

For `SECOND_BRAIN_GEMINI_API_KEY`, replace the value in `deploy/.env.prod`, then recreate the
services that call Gemini:

```bash
$DC up -d --force-recreate api worker
curl -fsS localhost:8000/health
```

For `SECOND_BRAIN_API_TOKEN`, replace the value in `deploy/.env.prod`, recreate `api`, then paste
the new token into the web sidebar key field and smoke-test `/chat` or `/search`.

```bash
$DC up -d --force-recreate api
curl -i -H "Authorization: Bearer <new-api-token>" "localhost:8000/search?q=smoke"
```

For `SECOND_BRAIN_ADMIN_TOKEN`, replace the value in `deploy/.env.prod`, recreate `api`, and test
one guarded endpoint with the new token. Use an existing source ID; the response must not be
`401 Unauthorized`.

```bash
$DC up -d --force-recreate api
curl -i -H "Authorization: Bearer <api-token>" \
  -H "X-Second-Brain-Admin-Token: <new-admin-token>" \
  "localhost:8000/data/export?source_id=<existing-source-id>"
```

For `POSTGRES_PASSWORD`, plan a short maintenance window, take a fresh backup first, and rotate
Postgres plus the API/worker environment together:

```bash
sudo /usr/local/sbin/second-brain-backup
read -r -s NEW_POSTGRES_PASSWORD
$DC exec -T db psql -U second_brain -d postgres -v "new_password=$NEW_POSTGRES_PASSWORD" -c "ALTER ROLE second_brain WITH PASSWORD :'new_password';"
# edit deploy/.env.prod: POSTGRES_PASSWORD=<new value>
$DC up -d --force-recreate api worker
curl -fsS localhost:8000/health
```

If a secret was leaked publicly, revoke it at the provider first where possible, rotate locally,
then check `git log`, shell history, and process logs for accidental exposure.

## Deployment rollback
For a bad app release, check out the previous green SHA and rebuild the existing Compose stack:

```bash
git checkout <previous-green-sha>
$DC up -d --build
curl -fsS localhost:8000/health
curl -fsS https://YOUR_VPS_IP.sslip.io/api/health
```

If a migration is involved, restore the pre-migration dump from `backup-restore.md` unless the
downgrade was tested. Prompt regressions can be rolled back faster by setting
`SECOND_BRAIN_PROMPT_VERSION=rag-v1` in `deploy/.env.prod` and recreating `api`.

## After any incident
Write 3 lines in `docs/PROGRESS.md`: what broke, how it was fixed, what would prevent it
(a new alert threshold, a guard, more swap). The audit log (`audit_log`) is the record of any
destructive action taken during the incident.
