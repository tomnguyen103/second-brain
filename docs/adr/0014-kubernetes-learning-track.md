# ADR-0014: Kubernetes learning track on local kind (manifests + HPA + ingress + CI/CD), then torn down

- **Status:** Accepted
- **Date:** 2026-06-02
- **Phase:** 7
- **Relates:** ADR-0012 (productionization), ADR-0015 (local-first runtime). This ADR does **not**
  change the default runtime — it adds a *learning track*.

## Context

ADR-0015 fixes the default runtime as **local-first Docker Compose**:
a single-user app gets no benefit from Kubernetes' multi-node scheduling/autoscaling/self-healing,
and managed K8s would create a recurring bill. But "can operate the app on real Kubernetes" is a
signal worth demonstrating. The roadmap therefore carved out Phase 7 as a
**learning track**: prove the stack runs on real K8s with proper manifests, then tear it down so it
costs nothing and is never the prod runtime. The input was the 8-service prod compose stack
(`deploy/docker-compose.prod.yml`): `db`, `pgbouncer`, `redis`, `api`, `worker`, `frontend`,
`prometheus`, `grafana`.

## Decision

Translate the stack to real Kubernetes manifests (`deploy/k8s/`) and prove it on a free, local,
**multi-node `kind`** cluster, capturing evidence per layer (`docs/k8s-evidence/`), then **delete the
cluster** (D10). Key decisions (full list D1–D13 in `docs/phase-7-plan.md`):

- **D1** Cluster = multi-node `kind` (1 control-plane + 2 workers) so HPA pod-spread and
  ingress-on-a-labelled-node are real, not single-node toys.
- **D2** Images built locally and `kind load`ed (no registry, $0); fixed `:phase7` tag +
  `imagePullPolicy: IfNotPresent` so K8s never attempts a registry pull.
- **D3** Postgres = StatefulSet + PVC; `alembic upgrade head` runs as a one-shot **Job** against the
  DB directly (not via pgbouncer) — split out of the api's compose `command`.
- **D4** Config split: ConfigMap (non-secret) + Secret (DB password, admin token, Gemini key,
  Grafana password). **Secrets are never committed** — only `secret.example.yaml`; the real Secret
  is created out-of-band. The password stays out of DSNs by `$(VAR)` env assembly per pod.
- **D5** Ingress = ingress-nginx, host-based (`api.second-brain.local`, `second-brain.local`).
- **D6** Autoscaling = metrics-server + HPA on api CPU; demonstrated under `hey` load.
- **D7** Observability = Prometheus + Grafana reused verbatim from Phase 6 configs (no RAM trim needed).
- **D8** New CI workflow `k8s.yml` (kind-action) stands the stack up and tears it down; the
  eval-gated `ci.yml` is untouched.
- **D9** Managed cloud (GKE/EKS) = OFF by default; no paid resource without explicit approval.
- **D10** Teardown after evidence: `kind delete cluster`.
- **D11 (added)** `NEXT_PUBLIC_API_BASE_URL` is build-time baked (Next inlines `NEXT_PUBLIC_*` at
  `next build`); `Dockerfile.frontend` gains an additive, default-preserving build `ARG` so the K8s
  image bakes the ingress API host.
- **D12 (added)** pgbouncer configured by env (edoburu auto-generates `userlist.txt`) so the DB
  password comes from the Secret, never a committed `userlist.txt`; SESSION pool mode kept.
- **D13 (added)** HPA load-scaling is proven **locally** (evidence 08); CI does
  build→load→apply→rollout→smoke→teardown only (deterministic, no flaky timing).

## Consequences

**Good**
- A real, reproducible K8s proof: StatefulSet+PVC, migrate Job, Deployments, ingress, HPA (scaled
  api 1→4 under load and back), Prometheus scraping the api, Grafana healthy — all captured.
- Manifests + a kind CI workflow are committed and recreate the stack on demand; nothing runs idle.
- Surfaced + fixed a latent Phase-6 image bug (no `.dockerignore` → host `.venv`/`node_modules`
  shipped into the images); the prod images were only `docker compose config`-linted before, never built.
- Demonstrates engineering judgment: knowing when **not** to run K8s in production is itself a signal.

**Bad / trade-offs**
- The manifests are a learning artifact, not the prod runtime — they drift from compose unless kept
  in sync (mitigated: monitoring configs are reused `--from-file`, not duplicated).
- The backend image uses CPU-only Torch wheels for the small-VPS runtime; K8s remains a learning
  artifact and can still drift from Compose unless reviewed before reuse.
- HPA scaling isn't gated in CI (D13) — demonstrated locally instead.

## Alternatives rejected

- **Run K8s in production (managed GKE/EKS).** Rejected: cost ($70+/mo vs ~$5) and complexity for a
  single-user app. (D9 keeps a managed-cluster capstone optional and off by default.)
- **k3s instead of kind.** Either works for the track; kind is the lighter, throwaway,
  CI-native choice (kind-action) and needs only the already-installed Docker Desktop.
- **Commit a rendered Secret / a pgbouncer `userlist.txt`.** Rejected: would leak credentials into
  git (D4/D12).
- **Single-node kind.** Rejected: HPA spread and ingress-ready node scheduling are more honest on
  multi-node (D1).
