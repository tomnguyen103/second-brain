# Runbook — Deploy to the VPS

The live deploy (deferred from Phase 6 until the box is provisioned per ADR-0011). Everything
runs as one Docker Compose stack on one VPS. Eval-gated: only deploy a commit whose CI is green.

## 0. Provision the box (ADR-0011)
- **Primary:** Oracle Cloud Always Free, **Singapore** region, VM.Standard.A1.Flex, 4 OCPU /
  24 GB / ~100 GB boot. ARM64 — our images are multi-arch.
- **Fallback:** Contabo Cloud VPS 10 (Singapore), 8 GB.
- Open only the ports you serve (see step 5). Add a swapfile if on 4 GB.

## 1. Install Docker + Compose
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # re-login
docker compose version
```

## 2. Clone + configure secrets
```bash
git clone <repo> second-brain && cd second-brain
cp deploy/.env.prod.example deploy/.env.prod
#   edit deploy/.env.prod — set POSTGRES_PASSWORD, SECOND_BRAIN_GEMINI_API_KEY,
#   SECOND_BRAIN_ADMIN_TOKEN (long random), GRAFANA_ADMIN_PASSWORD
```
`deploy/.env.prod` and `deploy/pgbouncer/userlist.txt` are gitignored — they never enter git.

## 3. Pre-flight: confirm CI is green (the eval gate)
Only deploy a commit whose GitHub Actions run passed — that means unit + integration tests and
the **eval quality gate** (`python -m app.eval.gate`) all passed. The gate blocks deploys whose
retrieval/citation quality regressed. Locally you can re-run it:
```bash
cd backend && python -m app.eval.gate    # exit 0 = quality OK
```

## 4. Bring up the DB first, then generate the PgBouncer userlist
```bash
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.prod up -d db
# wait for healthy, then copy the SCRAM verifier into the (gitignored) userlist:
cp deploy/pgbouncer/userlist.txt.example deploy/pgbouncer/userlist.txt
docker compose -f deploy/docker-compose.prod.yml exec db \
  psql -U second_brain -tAc \
  "SELECT '\"'||rolname||'\" \"'||rolpassword||'\"' FROM pg_authid WHERE rolname='second_brain';" \
  > deploy/pgbouncer/userlist.txt
```

## 5. Bring up the whole stack
```bash
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.prod up -d --build
```
The `api` service applies migrations (`alembic upgrade head`, against the DB directly — not via
PgBouncer) then starts uvicorn. Services: db, pgbouncer (6432), redis, api (8000), frontend
(3000), prometheus (9090), grafana (3001). Put a reverse proxy (Caddy/Traefik) + TLS in front;
only expose 80/443 publicly, keep 9090/3001 behind the proxy or an SSH tunnel.

## 6. Verify
```bash
curl -s localhost:8000/health        # {"status":"ok","db":"ok",...}
curl -s localhost:8000/metrics | head
#   Grafana http://<host>:3001 (admin / GRAFANA_ADMIN_PASSWORD) → "Second Brain — service overview"
#   Prometheus http://<host>:9090/alerts → rules loaded
```

## 7. Rollback
```bash
git checkout <previous-green-sha>
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.prod up -d --build
#   DB: only if a migration must be undone -> alembic downgrade -1 (see backup-restore first)
#   Prompt rollback needs no deploy: set SECOND_BRAIN_PROMPT_VERSION=rag-v1 and restart api (ADR-0009)
```

## Update flow (steady state)
`git pull` a green commit → `up -d --build` → verify `/health` + Grafana. Take a DB backup
before any release that includes a migration (see `backup-restore.md`).
