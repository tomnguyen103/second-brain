# Kubernetes learning track (local `kind`) — Phase 7

> **Kubernetes here is a LEARNING TRACK, not the production runtime.** Production stays the
> single-VPS Docker Compose stack (`deploy/docker-compose.prod.yml`, ADR-0011/0012). These
> manifests prove the app runs on real K8s (StatefulSet, Job, Deployments, ingress, HPA,
> monitoring), then the cluster is **torn down** so nothing keeps running ($0). See ADR-0014 and
> `docs/phase-7-plan.md`. Evidence captured under `docs/k8s-evidence/`. CI: `.github/workflows/k8s.yml`.

The 8 prod-compose services map to: `db` → StatefulSet+PVC, migrations → a Job, `pgbouncer`/`redis`/
`api`/`worker`/`frontend`/`prometheus`/`grafana` → Deployments, plus an Ingress and an HPA on `api`.

## Prerequisites
- Docker Desktop (WSL2) running. `kind` + `kubectl` (`winget install Kubernetes.kind`; kubectl ships with Docker Desktop).
- The in-cluster Postgres is **separate** from any host Postgres (e.g. the dev DB on host :5433).

## 1. Create the cluster (multi-node, ingress-ready)
```bash
kind create cluster --name second-brain --config deploy/k8s/kind-cluster.yaml
```

## 2. Build images and load them into the cluster (no registry, D2)
```bash
docker build -f deploy/Dockerfile.backend  -t second-brain-api:phase7 .
docker build -f deploy/Dockerfile.frontend -t second-brain-web:phase7 \
  --build-arg NEXT_PUBLIC_API_BASE_URL=http://api.second-brain.local .   # D11: baked at build time
kind load docker-image second-brain-api:phase7 --name second-brain
kind load docker-image second-brain-web:phase7 --name second-brain
```

## 3. Create the Secret (NOT committed, D4) + the monitoring ConfigMaps (from the Phase 6 configs)
```bash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl -n second-brain create secret generic second-brain-secrets \
  --from-literal=POSTGRES_PASSWORD='second_brain' \
  --from-literal=SECOND_BRAIN_ADMIN_TOKEN='phase7-admin-token' \
  --from-literal=SECOND_BRAIN_GEMINI_API_KEY='' \
  --from-literal=GRAFANA_ADMIN_PASSWORD='admin'

kubectl -n second-brain create configmap prometheus-config \
  --from-file=prometheus.yml=deploy/prometheus/prometheus.yml \
  --from-file=alerts.yml=deploy/prometheus/alerts.yml --dry-run=client -o yaml | kubectl apply -f -
kubectl -n second-brain create configmap grafana-datasources \
  --from-file=deploy/grafana/provisioning/datasources/datasource.yml --dry-run=client -o yaml | kubectl apply -f -
kubectl -n second-brain create configmap grafana-dashboard-provider \
  --from-file=deploy/grafana/provisioning/dashboards/dashboards.yml --dry-run=client -o yaml | kubectl apply -f -
kubectl -n second-brain create configmap grafana-dashboard-json \
  --from-file=deploy/grafana/dashboards/second-brain.json --dry-run=client -o yaml | kubectl apply -f -
```

## 4. Cluster add-ons (pinned)
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.3/deploy/static/provider/kind/deploy.yaml
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.7.2/components.yaml
kubectl -n kube-system patch deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'   # kind needs this
kubectl wait -n ingress-nginx --for=condition=ready pod -l app.kubernetes.io/component=controller --timeout=180s
```

## 5. Apply the stack
```bash
kubectl apply -k deploy/k8s     # one-shot (Secret + monitoring ConfigMaps from step 3 are prerequisites)
# Wait for everything:
kubectl -n second-brain rollout status statefulset/db
kubectl -n second-brain wait --for=condition=complete job/migrate --timeout=300s
for d in pgbouncer redis api worker frontend prometheus grafana; do kubectl -n second-brain rollout status deploy/$d; done
```

## 6. Verify (smoke through ingress — host 80 maps to the cluster)
```bash
curl -H 'Host: api.second-brain.local' http://localhost/health        # {"status":"ok","db":"ok",...}
curl -L -H 'Host: second-brain.local'  http://localhost/              # UI (/, 307 -> /chat, 200 HTML)
```
For a browser, add to your hosts file: `127.0.0.1  second-brain.local api.second-brain.local`.

## 7. HPA autoscaling demo (D6)
```bash
kubectl -n second-brain run load --image=williamyeh/hey --restart=Never -- -z 90s -c 80 http://api:8000/health
watch kubectl -n second-brain get hpa api          # CPU climbs past 50%; api scales 1 -> 4
kubectl -n second-brain delete pod load --now      # then api scales 4 -> 1
```

## 8. Teardown (D10 — leave nothing running, $0)
```bash
kind delete cluster --name second-brain
```
