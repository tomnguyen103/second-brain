# Kubernetes Learning Track (local kind)

> Kubernetes here is a learning track, not the production runtime. Production stays the single-VPS
> Docker Compose stack. These manifests prove the core app runs on local Kubernetes, then the
> cluster is torn down so nothing keeps running or costs money.

The default `kubectl apply -k deploy/k8s` path runs the core stack only: `db`, migrations, `redis`,
`api`, `worker`, `frontend`, ingress, and the API HPA. PgBouncer and Prometheus/Grafana runtime
containers are not part of the default apply because their public vendor images produced unresolved
CVE findings during the security review.

## Prerequisites

- Docker Desktop running.
- `kind` and `kubectl`.
- The in-cluster Postgres is separate from any host Postgres, such as the dev DB on `:5433`.

## 1. Create The Cluster

```bash
kind create cluster --name second-brain --config deploy/k8s/kind-cluster.yaml
```

## 2. Build And Load Local Images

```bash
docker build -f deploy/Dockerfile.pgvector -t second-brain-pgvector:phase7 .
docker build -f deploy/Dockerfile.backend -t second-brain-api:phase7 .
docker build -f deploy/Dockerfile.frontend -t second-brain-web:phase7 \
  --build-arg NEXT_PUBLIC_API_BASE_URL=http://api.second-brain.local .

kind load docker-image second-brain-pgvector:phase7 --name second-brain
kind load docker-image second-brain-api:phase7 --name second-brain
kind load docker-image second-brain-web:phase7 --name second-brain
```

## 3. Create The Secret

```bash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl -n second-brain create secret generic second-brain-secrets \
  --from-literal=POSTGRES_PASSWORD='<choose-one>' \
  --from-literal=SECOND_BRAIN_API_TOKEN='<choose-one>' \
  --from-literal=SECOND_BRAIN_ADMIN_TOKEN='<choose-one>' \
  --from-literal=SECOND_BRAIN_GEMINI_API_KEY=''
```

## 4. Install Add-Ons

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.3/deploy/static/provider/kind/deploy.yaml
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.7.2/components.yaml
kubectl -n kube-system patch deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl wait -n ingress-nginx --for=condition=ready pod -l app.kubernetes.io/component=controller --timeout=180s
```

## 5. Apply And Verify

```bash
kubectl apply -k deploy/k8s
kubectl -n second-brain rollout status statefulset/db
kubectl -n second-brain wait --for=condition=complete job/migrate --timeout=300s
for d in redis api worker frontend; do kubectl -n second-brain rollout status deploy/$d; done

curl -H 'Host: api.second-brain.local' http://localhost/health
curl -L -H 'Host: second-brain.local' http://localhost/
```

For a browser, add to your hosts file:

```text
127.0.0.1  second-brain.local api.second-brain.local
```

## Optional Monitoring Templates

`deploy/k8s/monitoring/` still contains Prometheus/Grafana templates and the shared configs remain
under `deploy/prometheus/` and `deploy/grafana/`. Those manifests intentionally use local
`*-clean-required` image tags with `imagePullPolicy: Never`; build and scan clean local images before
applying them.

Example local-only flow:

```bash
# Build or import locally maintained, pinned Prometheus/Grafana images first, then tag them for
# the learning manifests. Keep the source Dockerfiles or provenance notes out of this default
# runtime until they scan clean.
docker tag <scanned-clean-prometheus-image> second-brain-prometheus:phase7-clean-required
docker tag <scanned-clean-grafana-image> second-brain-grafana:phase7-clean-required
trivy image --severity CRITICAL,HIGH --exit-code 1 second-brain-prometheus:phase7-clean-required
trivy image --severity CRITICAL,HIGH --exit-code 1 second-brain-grafana:phase7-clean-required
kind load docker-image second-brain-prometheus:phase7-clean-required --name second-brain
kind load docker-image second-brain-grafana:phase7-clean-required --name second-brain
kubectl apply -f deploy/k8s/monitoring/
```

Redis is pinned to a Redis 7.4 Alpine digest in this learning-track manifest. Second Brain uses
Redis only for cache/rate-limit commands, not Lua scripts, ACL loading, bit operations, or durable
RDB persistence; the CI kind smoke plus backend cache/rate-limit tests are the verification path.

## Teardown

```bash
kind delete cluster --name second-brain
```
