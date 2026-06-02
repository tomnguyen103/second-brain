# Runbook — Incident response

Single-user app on one box, so "incident response" = a short triage loop. Start at the
Grafana "Second Brain — service overview" dashboard and the Prometheus alerts.

## Triage order
1. `curl -s localhost:8000/health` → is `db` `ok`?
2. `docker compose -f deploy/docker-compose.prod.yml ps` → which containers are up/healthy?
3. `docker compose ... logs --tail=200 <service>` → recent errors.
4. Grafana dashboard → request rate, p95 latency, 5xx ratio, API up.

## Alert → likely cause → action

### `ApiDown` (Prometheus can't scrape the API)
- `docker compose ... ps api` / `logs api`. Common: DB not healthy yet, or a bad migration on
  the startup `alembic upgrade head` step.
- DB down → see "DB unreachable". Migration failure → restore pre-migrate dump
  (`backup-restore.md`) or `alembic downgrade -1`, then redeploy a green commit.

### `HighErrorRate` (5xx > 5%)
- `logs api` for tracebacks. If it started after a deploy → roll back to the previous green SHA
  (`deploy-checklist.md` §7).
- If Gemini-related (quota/timeout): flip to private mode `SECOND_BRAIN_LLM_PROVIDER=ollama`
  (if Ollama is present) or wait out the quota; chat refuses gracefully on no-context.

### `HighLatencyP95` (p95 > 2s)
- Usually the LLM call (Gemini) — check `chat` latency in messages / Grafana. Embedding/retrieval
  is sub-ms locally (see `docs/query-optimization.md`).
- DB slow? Check connections: PgBouncer pool exhausted → raise `default_pool_size`, or a missing
  index after a schema change → `EXPLAIN ANALYZE` the slow query.

### DB unreachable
- `docker compose ... logs db`. Disk full is the classic cause: `df -h`; prune old WAL/backups,
  Docker images (`docker system prune`). On 4 GB boxes, OOM can kill Postgres — check `dmesg`,
  add swap, lower Prometheus retention.

## Bad retrieval / hallucination spike
- Not an outage but a quality regression. Re-run the eval gate against the corpus
  (`python -m app.eval.gate`) and the real A/B (`python -m app.eval.runner --configs gemini`).
- If a prompt change caused it: roll the prompt back instantly — `SECOND_BRAIN_PROMPT_VERSION=rag-v1`
  and restart `api` (no redeploy; ADR-0009).

## Data-subject request (GDPR)
- Export: `GET /data/export?source_id=<id>` with the admin bearer token.
- Erase: `DELETE /data/sources/{id}` (cascades; audited). Both require `SECOND_BRAIN_ADMIN_TOKEN`.

## After any incident
Write 3 lines in `docs/PROGRESS.md`: what broke, how it was fixed, what would prevent it
(a new alert threshold, a guard, more swap). The audit log (`audit_log`) is the record of any
destructive action taken during the incident.
