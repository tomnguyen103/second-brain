# Runbook — Deploy to the VPS

The live deploy (deferred from Phase 6 until the box is provisioned per ADR-0011). Everything
runs as one Docker Compose stack on one VPS. Eval-gated: only deploy a commit whose CI is green.

> **Status (2026-06-02): LIVE** on a DigitalOcean droplet (`YOUR_VPS_IP`), project
> `second-brain`, with a Caddy HTTPS reverse proxy (adds `deploy/docker-compose.vps.yml` +
> `deploy/caddy/Caddyfile` on top of the base). To **operate the running box**, see
> **`docs/USAGE.md`**; this runbook stays the from-scratch provisioning reference. Every prod
> compose command must use:
> `docker compose -p second-brain -f deploy/docker-compose.prod.yml -f deploy/docker-compose.vps.yml --env-file deploy/.env.prod …`

## 0. Provision the box (ADR-0011, amended 2026-06-02 — US-based owner)
- **Primary:** Oracle Cloud Always Free, **US Central (Chicago, `us-chicago-1`)** home region,
  VM.Standard.A1.Flex, up to 4 OCPU / 24 GB / ~100 GB boot. ARM64 — our images are multi-arch.
- **Fallback:** Hetzner US (Ashburn VA / Hillsboro OR), ~$5/mo, x86 — instant, no ARM-capacity lottery.
- Open only the ports you serve (see step 5). Add a swapfile if on a small (≤4 GB) box.

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
#   edit deploy/.env.prod — set POSTGRES_PASSWORD, SECOND_BRAIN_API_TOKEN,
#   SECOND_BRAIN_GEMINI_API_KEY, optional SECOND_BRAIN_ADMIN_TOKEN
```
`deploy/.env.prod` is gitignored — real secrets never enter git.

## 3. Pre-flight: confirm CI is green (the eval gate)
Only deploy a commit whose GitHub Actions run passed — that means unit + integration tests and
the **eval quality gate** (`python -m app.eval.gate`) all passed. The gate blocks deploys whose
retrieval/citation quality regressed. Locally you can re-run it:
```bash
cd backend && python -m app.eval.gate    # exit 0 = quality OK
```

## 4. Configure the host firewall (ufw)
Keep the current SSH session open while enabling `ufw`; verify a second SSH session works before
closing it. The public surface is Caddy on 80/443 plus SSH on 22. The direct API/frontend ports stay
bound to localhost by `deploy/docker-compose.vps.yml`.

```bash
sudo apt-get update
sudo apt-get install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment "ssh"
sudo ufw allow 80/tcp comment "http-caddy"
sudo ufw allow 443/tcp comment "https-caddy"
sudo ufw --force enable
sudo ufw status verbose
```

Expected public allow list:

```text
22/tcp   ALLOW IN
80/tcp   ALLOW IN
443/tcp  ALLOW IN
```

If an earlier experiment opened app or monitoring ports, remove them:

```bash
sudo ufw status numbered
sudo ufw delete <rule-number>
```

Do not allow 3000, 8000, 5432, 5433, or 6379 from the public internet.

## 5. Bring up the whole stack
```bash
DC="docker compose -p second-brain -f deploy/docker-compose.prod.yml -f deploy/docker-compose.vps.yml --env-file deploy/.env.prod"

$DC up -d --build
```
The `api` service applies migrations (`alembic upgrade head`, against the DB directly) then starts
uvicorn. Default services: db, redis, api (8000), worker, frontend (3000), and caddy (80/443).
Caddy is the public HTTPS entrypoint; the base file and VPS override keep direct app ports bound
to localhost. The API exposes Prometheus-format metrics at `/metrics`; production Compose does not
start Prometheus/Grafana containers until a scanned-clean runtime is selected.

## 6. Verify
```bash
curl -s localhost:8000/health        # {"status":"ok","db":"ok",...}
curl -s localhost:8000/metrics | head
```

Additional health checks:

```bash
$DC ps
curl -fsS localhost:8000/health
curl -fsS https://YOUR_VPS_IP.sslip.io/api/health
$DC exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
$DC exec -T redis redis-cli ping
$DC exec -T db sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;"'
```

Prometheus/Grafana configs remain in `deploy/prometheus/` and `deploy/grafana/`, but production
Compose no longer includes monitoring containers because the current upstream vendor images scanned
with critical/high CVE findings. Reintroduce monitoring only with scanned-clean images or custom
builds.

## 7. Schedule the daily briefing (OS cron — ADR-0013 D2)
The `worker` service drains the jobs queue continuously; a host cron line enqueues the
`briefing` job once a day. No resident scheduler (no APScheduler/pg_cron) — `$0`, one box.
```cron
# /etc/cron.d/second-brain-briefing  — 07:00 server time, daily
# /etc/cron.d format requires a user field (here: root) between the schedule and the command.
0 7 * * *  root  cd /root/second-brain && docker compose -p second-brain -f deploy/docker-compose.prod.yml -f deploy/docker-compose.vps.yml --env-file deploy/.env.prod exec -T worker python -m app.jobs.enqueue briefing >> /var/log/second-brain-briefing.log 2>&1
```
Read it next morning at `GET /briefing` (or the frontend page). Each run summarizes documents
ingested since the previous briefing's `period_end`; a re-run over an empty tail is a cheap
"nothing new" briefing (no LLM call), so an accidental double-enqueue is harmless. Inspect the
queue any time: `SELECT id,type,status,attempts,last_error FROM jobs ORDER BY id DESC LIMIT 10;`
(`status='failed'` is the dead-letter view).

## 8. Install automated DB backup cron
Install the checked-in backup template, create a private backup directory, and schedule a nightly
logical dump. This uses the existing VPS disk and adds no recurring cost.

```bash
cd /root/second-brain
sudo install -m 0750 deploy/cron/second-brain-backup /usr/local/sbin/second-brain-backup
sudo mkdir -p /var/backups/second-brain
sudo chmod 700 /var/backups/second-brain
echo '17 2 * * * root /usr/local/sbin/second-brain-backup >> /var/log/second-brain-backup.log 2>&1' | sudo tee /etc/cron.d/second-brain-backup
sudo /usr/local/sbin/second-brain-backup
sudo ls -lh /var/backups/second-brain
sudo tail -n 50 /var/log/second-brain-backup.log
```

The script keeps 14 days by default. Change retention without editing the script by adding an
environment assignment to the cron line, for example
`SECOND_BRAIN_BACKUP_RETENTION_DAYS=30`. Run the restore drill in `backup-restore.md` after the
first successful backup and monthly after that.

## 9. Rollback
Use the previous green SHA from GitHub Actions. For app-only regressions:

```bash
git checkout <previous-green-sha>
DC="docker compose -p second-brain -f deploy/docker-compose.prod.yml -f deploy/docker-compose.vps.yml --env-file deploy/.env.prod"

$DC up -d --build
curl -fsS localhost:8000/health
```

If the bad release included a migration, prefer restoring the pre-migration dump from
`backup-restore.md`. Only run `alembic downgrade -1` when the downgrade was tested and is known
not to destroy wanted data; run it while the migration code is still checked out:

```bash
$DC run --rm --no-deps api alembic downgrade -1
git checkout <previous-green-sha>
$DC up -d --build
curl -fsS localhost:8000/health
```

Prompt rollback needs no deploy: set `SECOND_BRAIN_PROMPT_VERSION=rag-v1` in
`deploy/.env.prod`, then `$DC up -d --force-recreate api` (ADR-0009).

## Update flow (steady state)
`git pull` a green commit → run the canonical `$DC up -d --build` command above → verify
`/api/health` + Grafana. Take a DB backup before any release that includes a migration (see
`backup-restore.md`).
