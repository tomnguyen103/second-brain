# Phase 7 — Kubernetes learning track (local kind) Implementation Plan

> **Not pytest-TDD.** Verification here is **"apply manifest → assert rollout / health / scale"**,
> not red→green. Each task ends with an explicit *verify gate* (a command + the expected
> observation). Build incrementally, apply+verify each layer before the next, commit per green
> layer. Capture evidence as text (`kubectl` output) under `docs/k8s-evidence/`.

**Goal (per AGENTS.md):** prove the Second Brain stack runs on **real Kubernetes** — proper
manifests, a Postgres StatefulSet, a migrate Job, Deployments for api/worker/frontend, host-based
**ingress**, **HPA** autoscaling under load, reused **Prometheus + Grafana**, and a **CI/CD**
workflow that stands the whole thing up on `kind` and tears it down — then **`kind delete cluster`**
so **nothing is left running ($0)**. Kubernetes is a **LEARNING TRACK only**, *not* the production
runtime (that stays the single-VPS Docker Compose stack, ADR-0011/0012). Managed cloud (GKE/EKS) is
**off by default** (D9) — no paid resource without an explicit OK.

**Scope reality:** this mirrors how Phases 1–6 deferred their out-of-scope tails. The deliverable is
**manifests + CI + docs + captured evidence**, proven on a *throwaway* local cluster. The cluster
itself is ephemeral; the committed artifacts are the durable output. We translate the 8 prod-compose
services (`deploy/docker-compose.prod.yml`): `db`, `pgbouncer`, `redis`, `api`, `worker`, `frontend`,
`prometheus`, `grafana`.

**Architecture (Compose → K8s mapping):**

| Compose service | K8s object(s) | Notes |
|---|---|---|
| `db` (pgvector:pg16) | **StatefulSet** + headless Service + **PVC** | `pg_isready` readiness; `db` Service DNS = `db.second-brain.svc` |
| (migrations) | **Job** `migrate` (`alembic upgrade head`) | Was the api compose `command` prefix; now its own Job → DB **directly** (not via pgbouncer), per D3 |
| `pgbouncer` | **Deployment** + Service `:6432` | `edoburu/pgbouncer` configured by **env** (DB_HOST/USER/PASSWORD) — auto-generates userlist, so no password file is committed (divergence from compose's mounted `userlist.txt`; see D12) |
| `redis` | **Deployment** + Service `:6379` | In-memory, `allkeys-lru`; app treats it as optional cache (no readiness gate on it) |
| `api` (Dockerfile.backend) | **Deployment** (HPA target) + Service `:8000` | Runs **only** `uvicorn` (migrations moved to the Job); CPU `requests` set so HPA can compute % |
| `worker` (Dockerfile.backend) | **Deployment** (1 replica) | `python -m app.jobs.worker --loop`; same image/env; no ports |
| `frontend` (Dockerfile.frontend) | **Deployment** + Service `:3000` | `NEXT_PUBLIC_API_BASE_URL` is **build-time baked** (D11) |
| `prometheus` | **Deployment** + Service `:9090` + ConfigMap | `prometheus.yml`/`alerts.yml` from existing `deploy/prometheus/*` as a ConfigMap |
| `grafana` | **Deployment** + Service `:3000` + ConfigMap | provisioning + dashboard JSON as ConfigMaps; admin pw from Secret |
| (north-south) | **Ingress** (ingress-nginx) | host-based: `second-brain.local` → frontend, `api.second-brain.local` → api |
| (autoscaling) | **metrics-server** + **HPA** | HPA on api CPU; load via `hey`/`kubectl run` |

**Tech delta:** no application-code changes. New top-level `deploy/k8s/` (manifests, kustomization,
`secret.example.yaml`), a new `.github/workflows/k8s.yml`, `docs/k8s-evidence/`, ADR-0014. The
existing eval-gated `ci.yml` is **untouched**. One additive, backwards-compatible change to
`deploy/Dockerfile.frontend` (a build `ARG`, see D11). `kind` + `kubectl` installed via winget if
missing (D1).

## Decisions

**D1–D10 are the goal's defaults (accepted).** **D11–D13 are decisions this plan adds** after
reading the stack — flagged here rather than discovered mid-build.

- **D1 — Cluster = `kind`, multi-node** (1 control-plane + 2 workers) so HPA spread and
  ingress-on-a-labelled-node are real, not single-node toys. Install `kind`+`kubectl` via winget if
  absent (Docker Desktop/WSL2 already present). Cluster config carries `extraPortMappings` 80/443→host
  and `ingress-ready=true` on the control-plane node.
- **D2 — Images built locally + `kind load docker-image`** (no registry, $0). Tag `…:phase7` (a
  fixed non-`latest` tag) with **`imagePullPolicy: IfNotPresent`** so K8s uses the loaded image and
  never tries a registry pull.
- **D3 — Postgres = StatefulSet + PVC** (`pgvector/pgvector:pg16`), reached in-cluster by Service DNS.
  `alembic upgrade head` runs as a **migrate Job** (against the DB **directly**, mirroring the compose
  `DIRECT_DATABASE_URL`), not inline in the api. api/worker wait on DB via an init wait + the Job is
  applied and `kubectl wait`-ed before they roll.
- **D4 — Config split: ConfigMap (non-secret) + Secret (secret).** ConfigMap: in-cluster DSNs (Service
  DNS), `SECOND_BRAIN_LLM_PROVIDER`, `NEXT_PUBLIC_API_BASE_URL`. Secret: DB password, Gemini API key,
  admin token, Grafana admin password. **Secrets are never committed** — ship `secret.example.yaml`
  only; the real Secret is created out-of-band (documented).
- **D5 — Ingress = ingress-nginx**, host-based to api + frontend; smoke `GET /health` through it.
- **D6 — Autoscaling = metrics-server + HPA on api (CPU target).** Demonstrate scale-up under load
  (`hey`/`kubectl run … hey`), capture `kubectl get hpa` + pod count before/after as evidence.
- **D7 — Observability = reuse Prometheus + Grafana as simple Deployments**, configs via ConfigMap.
  Trim (e.g. drop Grafana, keep Prometheus) **only** if local RAM forces it — and note the trim.
- **D8 — CI/CD = new GitHub Actions workflow** (`k8s.yml`, kind action): build+load images, install
  ingress-nginx, apply manifests, `kubectl wait` rollouts, smoke `/health` through ingress, tear down.
  The existing eval-gated `ci.yml` stays untouched and green. **HPA load demo stays a *local* evidence
  step (D13)** — not in CI.
- **D9 — Managed cluster (GKE/EKS) = OPTIONAL, OFF BY DEFAULT.** No paid cloud resource without
  flagging cost and waiting for an explicit OK (AGENTS.md cost rule). If ever approved → delete
  immediately after.
- **D10 — Teardown:** after evidence is captured, `kind delete cluster`; nothing left running.

- **D11 (ADDED) — `NEXT_PUBLIC_API_BASE_URL` is build-time baked; add a backwards-compatible build
  `ARG` to `Dockerfile.frontend`.** Next.js inlines `NEXT_PUBLIC_*` at `next build`, so a runtime
  ConfigMap value can't change what the browser fetches. The compose stack happens to pass it at
  runtime (works only because compose's default points at `localhost:8000`). For K8s the browser must
  call the API's **ingress** host, so the frontend image is **built with**
  `NEXT_PUBLIC_API_BASE_URL=http://api.second-brain.local`. Implemented as `ARG
  NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` + `ENV` before `npm run build` — **additive and
  default-preserving** (compose builds with no arg → unchanged behaviour). *Trade-off:* one Phase-6
  file touched, but only additively; recorded in implementation-notes.
- **D12 (ADDED) — pgbouncer configured by env, not a committed `userlist.txt`.** The compose stack
  mounts `pgbouncer/userlist.txt`, which embeds the DB credential — committing that to a manifest/
  ConfigMap would leak a secret. `edoburu/pgbouncer` supports env config (`DB_HOST/DB_USER/
  DB_PASSWORD/POOL_MODE=session`) and auto-generates the userlist at start. So pgbouncer reads
  password from the **Secret** via env. *Trade-off:* diverges from the file-mounted compose config,
  but keeps the secret out of git and preserves session pooling (ADR-0012 — psycopg3 prepared
  statements need session mode).
- **D13 (ADDED) — HPA scale-up evidence is captured *locally*, committed under `docs/k8s-evidence/`;
  CI does build→load→apply→rollout→smoke→teardown only.** A load-driven autoscale is timing-sensitive
  and the backend image carries torch (slow to build + RAM-heavy per replica); making CI assert "pods
  went 1→N" would be flaky. CI proves the manifests *stand up and serve*; the autoscaling proof is the
  local evidence artifact. *Trade-off:* CI doesn't gate on scaling — acceptable for a learning track;
  the scaling is demonstrated + captured, just not in the pipeline.

## File structure (created/modified in this phase)

```text
deploy/
  Dockerfile.frontend                  # MODIFY (D11): additive ARG NEXT_PUBLIC_API_BASE_URL
  k8s/
    kind-cluster.yaml                  # CREATE: multi-node kind config (extraPortMappings, ingress-ready)
    namespace.yaml                     # CREATE: namespace second-brain
    configmap.yaml                     # CREATE: non-secret config (DSNs, provider, api base url)
    secret.example.yaml                # CREATE: TEMPLATE only (no real secrets committed)
    postgres-statefulset.yaml          # CREATE: StatefulSet + headless Service + PVC
    migrate-job.yaml                    # CREATE: Job alembic upgrade head (direct DSN)
    pgbouncer.yaml                      # CREATE: Deployment + Service :6432 (env-configured, D12)
    redis.yaml                          # CREATE: Deployment + Service :6379
    api.yaml                            # CREATE: Deployment (CPU requests) + Service :8000
    worker.yaml                         # CREATE: Deployment (--loop)
    frontend.yaml                       # CREATE: Deployment + Service :3000
    ingress.yaml                        # CREATE: host-based ingress → frontend + api
    api-hpa.yaml                        # CREATE: HorizontalPodAutoscaler (api, CPU)
    monitoring/
      prometheus.yaml                   # CREATE: Deployment + Service + ConfigMap (from deploy/prometheus/*)
      grafana.yaml                      # CREATE: Deployment + Service + ConfigMaps (provisioning + dashboard)
    kustomization.yaml                  # CREATE: orders core resources for `kubectl apply -k`
    README.md                          # CREATE: apply order + run/verify + teardown
.github/workflows/
  k8s.yml                              # CREATE: kind CI (build+load+apply+rollout+smoke+teardown)
docs/
  phase-7-plan.md                      # THIS FILE
  adr/0014-kubernetes-learning-track.md # CREATE
  adr/README.md                        # MODIFY: index 0014
  k8s-evidence/                        # CREATE: captured kubectl output (rollout, ingress smoke, HPA scale)
  PROGRESS.md  implementation-notes.md # MODIFY: phase-7 → complete + off-spec notes
README.md / backend README            # MODIFY: "Phase 7 — run & verify" section
```

## Tasks (apply → verify gate)

> Branch `phase-7-impl` off `main`. Commit `docs/phase-7-plan.md` **first**. Then one commit per green
> layer. Windows Git-Bash junk-file quirk: `git clean -f` before each commit, explicit `git add`.

0. **Plan + tooling.** Commit this plan. Verify/install `kind`+`kubectl` (winget). **Gate:** `kind
   version`, `kubectl version --client`, `docker version` all succeed. Commit `docs: phase-7 plan
   (K8s learning track) + D1–D13`.
1. **Cluster + namespace.** `kind-cluster.yaml` (multi-node, ingress-ready, port maps); create
   cluster; `namespace.yaml`. **Gate:** `kubectl get nodes` shows control-plane + 2 workers `Ready`;
   `kubectl get ns second-brain` exists. Commit `feat(k8s): multi-node kind cluster config + namespace`.
2. **Config + secrets.** `configmap.yaml` (Service-DNS DSNs, provider, api base url) +
   `secret.example.yaml` (template). Create the **real** Secret locally from the template (NOT
   committed). **Gate:** `kubectl get configmap second-brain-config` + `kubectl get secret
   second-brain-secrets` present; `git status` shows no real secret staged. Commit `feat(k8s):
   configmap + secret template (secrets uncommitted, D4)`.
3. **Postgres StatefulSet + migrate Job.** Build backend image + `kind load`. Apply
   `postgres-statefulset.yaml`; once Ready, apply `migrate-job.yaml`. **Gate:** pg pod `Ready` +
   `kubectl exec … pg_isready` ok; `kubectl wait --for=condition=complete job/migrate` and its logs
   show `alembic upgrade head` → a revision (`0004…`). Commit `feat(k8s): postgres statefulset + PVC +
   migrate job`.
4. **pgbouncer + redis.** Apply both. **Gate:** both pods `Ready`; `kubectl exec` a `psql` through
   `pgbouncer:6432` returns `SELECT 1`; redis `PING`→`PONG`. Commit `feat(k8s): pgbouncer (env-config,
   D12) + redis`.
5. **api + worker.** `kind load` (reuse image). Apply `api.yaml` (CPU requests) + `worker.yaml`.
   **Gate:** `kubectl rollout status deploy/api` + `deploy/worker` complete; `kubectl port-forward
   svc/api 8000` → `curl /health` 200; worker logs show "no eligible job" (clean idle). Commit
   `feat(k8s): api + worker deployments`.
6. **frontend.** Build frontend image **with the ingress api host baked** (D11) + `kind load`. Apply
   `frontend.yaml`. **Gate:** `kubectl rollout status deploy/frontend`; port-forward → `curl /` serves
   HTML. Commit `feat(k8s): frontend deployment (NEXT_PUBLIC baked, D11)`.
7. **Ingress.** Install ingress-nginx (kind provider manifest), wait for the controller; apply
   `ingress.yaml`. **Gate:** `curl -H 'Host: api.second-brain.local' http://localhost/health` → 200;
   `curl -H 'Host: second-brain.local' http://localhost/` → frontend HTML. Capture both to evidence.
   Commit `feat(k8s): ingress-nginx host-based routing to api + frontend`.
8. **metrics-server + HPA + load demo.** Install metrics-server (`--kubelet-insecure-tls` for kind);
   apply `api-hpa.yaml`. Drive load (`hey` against `/health` through the api Service). **Gate:**
   `kubectl top pods` returns metrics; `kubectl get hpa` shows CPU% climbing; api replicas scale
   above `minReplicas`. Capture `get hpa` + `get pods` before/under/after load → evidence. Commit
   `feat(k8s): metrics-server + api HPA + load-scale evidence`.
9. **Monitoring (Prometheus + Grafana).** ConfigMaps from `deploy/prometheus/*` + `deploy/grafana/*`;
   apply `monitoring/`. **Gate:** both pods `Ready`; Prometheus `/-/healthy` 200 and its api target is
   `up`; Grafana `/api/health` 200. Trim per D7 if RAM-bound (note it). Commit `feat(k8s): prometheus +
   grafana deployments (reused configs)`.
10. **CI/CD (`k8s.yml`).** kind-action workflow: build+load both images, install ingress-nginx, apply
    manifests, `kubectl wait` rollouts, smoke `/health` via ingress, then teardown. Inject dummy
    secrets via workflow env (no real keys). **Gate:** YAML parses (`actionlint`/local), and the
    workflow is **green on the PR** (alongside the untouched `ci.yml`). Commit `ci(k8s): kind
    build→apply→rollout→smoke→teardown workflow`.
11. **Teardown + docs.** `kind delete cluster`; confirm nothing runs. ADR-0014 + index; flip PROGRESS
    Phase 7 → ✅ (dated); off-spec notes (D11/D12/D13, any trims) in implementation-notes; README
    "Phase 7 — run & verify". **Gate:** `kind get clusters` empty / `docker ps` shows no kind/stack
    containers; docs updated. Commit `docs: phase-7 ADR-0014 + evidence + run/verify + progress;
    teardown`.

## Self-review (against AGENTS.md Phase 7 + the 8 services)

- Real manifests for all 8 compose services → Tasks 3–9 ✅ (db, pgbouncer, redis, api, worker, frontend, prometheus, grafana)
- StatefulSet + PVC for Postgres, migrations as a Job → Task 3 ✅
- Host-based ingress, /health smoked through it → Task 7 ✅
- HPA autoscaling demonstrated under load with captured evidence → Task 8 ✅
- Prometheus + Grafana reused → Task 9 ✅
- New K8s CI/CD workflow, existing eval CI untouched + green → Task 10 ✅
- Secrets not committed (template only) → Task 2 / D4 ✅
- Cluster torn down, $0, nothing left running → Task 11 / D10 ✅
- No paid cloud without explicit OK → D9 (off by default) ✅
- Docs: ADR-0014, PROGRESS dated, implementation-notes, README run/verify → Task 11 ✅

## Known sharp edges (flagged objections — not placeholders)

1. **Next.js `NEXT_PUBLIC_*` is build-time, not runtime (D11).** The browser→API call needs the
   ingress host baked at `next build`. Mitigation: additive build `ARG` on `Dockerfile.frontend`;
   smoke proves `/health` (api via ingress) **and** UI HTML served. Browser-driven UI→API is exercised
   via the baked host.
2. **kind never pulls loaded images.** Must use a fixed non-`latest` tag + `imagePullPolicy:
   IfNotPresent`, else K8s tries (and fails) a registry pull → `ImagePullBackOff`. (D2.)
3. **HPA needs CPU `requests` on api**, and metrics-server on kind needs `--kubelet-insecure-tls`.
   Without requests the HPA shows `<unknown>` and never scales.
4. **RAM on a laptop.** The backend image loads MiniLM/torch per replica; multiple api replicas +
   Prometheus + Grafana can pressure WSL2 memory. Mitigations: modest `requests`, HPA `maxReplicas`
   capped (≤4), drive the HPA with `/health` (no embedder load), trim monitoring per D7 if needed.
5. **Migrations are a Job, so api/worker must NOT migrate.** The api compose `command` prefixes
   `alembic upgrade head`; the K8s api runs *only* uvicorn. The Job runs once against the DB directly;
   api/worker tolerate a brief pre-migration race by restarting (same posture as the compose worker).
6. **pgbouncer secret handling (D12).** Use env-based config so the DB password comes from the Secret,
   never a committed `userlist.txt`. Session pool mode preserved (psycopg3 prepared statements).
7. **CI build time.** Building the torch-bearing backend image in CI is minutes-slow; acceptable, but
   the HPA load demo stays local (D13) to keep CI deterministic.
8. **Windows specifics.** Smoke uses `curl -H 'Host: …' http://localhost/…` (kind port-map) so no
   admin `hosts` edit is needed; the real `hosts` entry (`127.0.0.1 second-brain.local
   api.second-brain.local`) is documented for browser use. `git clean -f` + explicit `git add` guard
   the Git-Bash junk-file quirk.
