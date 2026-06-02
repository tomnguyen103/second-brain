# Phase 6 — Productionize + data-ops hardening Implementation Plan

> Work TDD (red → green → commit), DRY, YAGNI. Pure logic is DB-free unit-tested; services are
> integration-tested vs the real Postgres on 5433; deploy/observability artifacts are config,
> verified to parse/lint. Commit after each green task.

**Goal:** Turn the working app into something operable: **data governance** (RLS posture,
audit log, retention TTL, GDPR export + delete-my-data), **connection pooling** (PgBouncer),
**observability** (Prometheus metrics + Grafana dashboards + alert rules), an **eval-gated
CI/CD** pipeline (GitHub Actions blocks merge if answer quality regresses), and the **ops
docs** (deploy checklist, backup/restore + incident runbooks, query-tuning before/after).

**Scope reality:** the live VPS deploy is a **documented runbook**, not executed here — the box
is provisioned separately (ADR-0011). Everything in this phase is code/config that builds and
tests **without** a purchased server, mirroring how Phases 1–4 deferred their out-of-scope tails.

**Architecture:** keep the Phase 1 seams. New logic lives in **services that take a `db`
session** (`app/dataops/*`), tested with the rolled-back `db_session` fixture. Metrics are a
thin `app/obs/*` module + a `/metrics` route. Destructive/admin endpoints are guarded by a
bearer **admin token** dependency. RLS is enabled with a permissive policy (single-user today;
the tenant-scoping seam for later) so existing queries stay green while the governance
capability is demonstrable. Audit is **app-layer** (a service call), not DB triggers — portable
and unit/integration-testable.

**Tech delta:** `prometheus-client>=0.20,<1` (metrics). New migration `0003` (RLS + audit
hardening). New top-level `deploy/` (compose.prod, Dockerfiles, pgbouncer/prometheus/grafana
config) and `docs/runbooks/`. New `.github/workflows/ci.yml`.

## Decisions (recommended defaults, revisable — full rationale in ADR-0011 / ADR-0012)

- **D1 — VPS = Oracle Cloud Always Free (Singapore) primary, Contabo SG (~$5/mo, 8 GB) paid
  fallback.** Low cost is the priority and the app is SEA-local; Oracle is $0 + 24 GB + low
  latency, Contabo is the cheap reliable backstop. Hetzner is excellent but EU/US-only (latency).
  RAM is the binding constraint (Postgres + torch embedder + monitoring stack), not CPU (the LLM
  is offloaded to Gemini). *Recorded in ADR-0011.*
- **D2 — Audit log is written app-layer via a service, not DB triggers.** A `record(...)` call
  in the data-ops paths is portable, unit-testable, and explicit about *actor/action/entity*.
  *Gave up:* automatic capture of out-of-band SQL — acceptable for a single-user app where all
  writes go through the API/services.
- **D3 — RLS is enabled with a permissive (`USING (true)`) policy.** Demonstrates the governance
  mechanism + migration discipline without breaking the single-role app (owner-bypass + permissive
  policy keep all 79 existing tests green). The policy predicate is the documented seam for real
  per-tenant scoping if the app ever goes multi-user. *Gave up:* enforced row scoping now (no
  second user to scope against).
- **D4 — Retention nulls `documents.raw_text` after embedding + TTL; chunks/embeddings stay.**
  `raw_text` is the only PII-bearing free text retained post-ingest (the model already flags it
  "purged after embedding"); chunks are the retrieval units and must remain. Retrieval/citation
  code already tolerates a missing source row (`conversations.py` skips purged chunks). *Gave up:*
  hard-deleting chunks on TTL — that would break search; retention ≠ erasure.
- **D5 — Delete-my-data = delete a `source` (cascades to documents→chunks→embeddings via FK
  `ON DELETE CASCADE`) + an audit `delete` row; export returns the same subtree as JSON first.**
  Honest GDPR "right to erasure" + "right to access" at the source granularity (the unit the user
  actually added). *Gave up:* per-document UI — source-level is the natural ownership boundary.
- **D6 — CI eval gate uses the deterministic `fake` driver + retrieval/citation thresholds.**
  The gate must be reproducible and keyless in CI, so it asserts retrieval quality
  (`hit_at_k`, `citation_validity`, `refusal_accuracy`) which are LLM-independent (D2/ADR-0008).
  *Gave up:* gating on answer-text quality in CI — that needs the real `gemini` run (manual,
  documented). The gate is a pure `check_thresholds(...)` (unit-tested) + a `__main__` runner.
- **D7 — `docker-compose.prod.yml` is additive and never run in CI.** It composes db + pgbouncer
  + redis + api + frontend + prometheus + grafana for the VPS. Verified with `docker compose
  config` (parse/lint). The dev `docker-compose.yml` (db-only) is untouched. *Gave up:* a fully
  exercised prod stack in CI — too heavy; `config` lint + the deploy runbook cover it.

## File structure (created/modified in this phase)

```text
backend/
  requirements.txt                       # MODIFY: add prometheus-client
  app/
    config.py                            # MODIFY: phase-6 settings (admin_token, retention, metrics, audit)
    main.py                              # MODIFY: mount metrics middleware + /metrics + dataops router
    deps.py                              # MODIFY: require_admin token dependency
    dataops/__init__.py
    dataops/audit.py                     # CREATE: record(db, actor, action, entity_type, entity_id, detail)
    dataops/retention.py                 # CREATE: purge_raw_text(db, older_than_days) -> count
    dataops/erasure.py                   # CREATE: export_source / delete_source (+ audit)
    obs/__init__.py
    obs/metrics.py                       # CREATE: registry, counters/histograms, middleware, exposition
    api/dataops.py                       # CREATE: GET /data/export, DELETE /data/sources/{id}, POST /admin/retention/purge
    eval/gate.py                         # CREATE: check_thresholds(report, thresholds) + __main__ eval gate
  migrations/versions/0003_rls_audit.py  # CREATE: enable RLS + permissive policy on data tables
  tests/
    unit/test_config_phase6.py           # CREATE (DB-free): new settings defaults
    unit/test_metrics.py                 # CREATE (DB-free): registry + exposition
    unit/test_eval_gate.py               # CREATE (DB-free): threshold pass/fail
    integration/test_audit.py            # CREATE: audit round-trip
    integration/test_retention.py        # CREATE: purge nulls raw_text past TTL, audited
    integration/test_erasure.py          # CREATE: export subtree + delete cascade, audited
    integration/test_dataops_api.py      # CREATE: admin-guarded export/delete/purge via client
    integration/test_metrics_endpoint.py # CREATE: /metrics exposes text
  README.md                              # MODIFY: Phase 6 run/verify
deploy/
  Dockerfile.backend                     # CREATE: api image
  Dockerfile.frontend                    # CREATE: next build/start (or static)
  docker-compose.prod.yml                # CREATE: db + pgbouncer + redis + api + frontend + prometheus + grafana
  pgbouncer/pgbouncer.ini  userlist.txt  # CREATE: transaction pooling
  prometheus/prometheus.yml  alerts.yml  # CREATE: scrape api + alert rules
  grafana/provisioning/... dashboards/second-brain.json  # CREATE: datasource + dashboard
  .env.prod.example                      # CREATE: prod env template (no secrets)
.github/workflows/ci.yml                 # CREATE: lint + unit + integration (pg service) + eval gate
docs/
  adr/0011-vps-provider.md               # CREATE
  adr/0012-productionization-and-data-governance.md  # CREATE
  adr/README.md                          # MODIFY: index 0011/0012
  runbooks/deploy-checklist.md           # CREATE
  runbooks/backup-restore.md             # CREATE
  runbooks/incident-response.md          # CREATE
  query-optimization.md                  # CREATE: EXPLAIN ANALYZE before/after
  PROGRESS.md  implementation-notes.md   # MODIFY: phase-6 → complete + notes
```

## Tasks (TDD)

1. **Deps + config (DB-free).** Add `prometheus-client` to requirements. Add `Settings`:
   `admin_token: str | None`, `retention_raw_text_days: int = 180`, `metrics_enabled: bool = True`,
   `audit_enabled: bool = True`, `pgbouncer_url: str | None`. Unit-test defaults + env override.
   Commit `feat(config): phase-6 settings (admin token, retention, metrics, audit)`.
2. **Audit service (DB-bound).** `app/dataops/audit.py::record(db, *, actor, action, entity_type,
   entity_id=None, detail=None) -> AuditLog` (respects `audit_enabled`; flushes, no commit — caller
   owns the txn). Integration test: a record round-trips with the right columns; invalid action
   rejected by the existing CHECK. Commit `feat(dataops): audit-log service`.
3. **Retention service (DB-bound).** `app/dataops/retention.py::purge_raw_text(db, *,
   older_than_days) -> int` — set `raw_text = NULL` for `status='embedded'` docs whose
   `ingested_at < now() - interval`, return count, audit one `update`/`retention` row. Integration:
   ingest a doc, back-date `ingested_at`, purge, assert `raw_text IS NULL` + chunks intact + audited.
   Commit `feat(dataops): raw_text retention TTL`.
4. **Erasure service (DB-bound).** `app/dataops/erasure.py`: `export_source(db, source_id) -> dict`
   (source + documents + chunk counts as JSON, audit `export`) and `delete_source(db, source_id) ->
   int` (delete the source; FK cascade removes documents/chunks/embeddings; audit `delete`; raises if
   missing). Integration: export shape; delete removes the subtree and writes an audit row.
   Commit `feat(dataops): GDPR export + delete-my-data (source erasure)`.
5. **Admin guard + data-ops API (DB-bound).** `deps.require_admin` (compares `Authorization: Bearer`
   to `settings.admin_token`; 503 if unset, 401 if wrong). `app/api/dataops.py`: `GET /data/export?
   source_id=`, `DELETE /data/sources/{id}`, `POST /admin/retention/purge?older_than_days=`. Mount in
   `main.py`. Integration via `client`: unauthorized → 401/503; authorized → correct effects.
   Commit `feat(api): admin-guarded export / delete / retention endpoints`.
6. **Metrics (DB-free + endpoint).** `app/obs/metrics.py`: a `CollectorRegistry`, `http_requests_total`
   (method, path-template, status), `http_request_duration_seconds` histogram, `chat_latency_ms`
   summary, `ingest_documents_total`; an ASGI/HTTP middleware that times requests and records; a
   `render()` returning the exposition + content type. Mount middleware + `GET /metrics` in `main.py`
   (gated by `metrics_enabled`). Unit-test the registry (increment + exposition contains the metric);
   integration-test `/metrics` returns `text/plain; version=0.0.4`. Commit `feat(obs): Prometheus
   metrics + /metrics endpoint`.
7. **Migration 0003 — RLS + audit hardening (DB-bound).** Hand-written like 0002: `ALTER TABLE …
   ENABLE ROW LEVEL SECURITY` + `CREATE POLICY … USING (true)` on `sources, documents, chunks,
   embeddings, conversations, messages, retrievals, feedback`; downgrade drops policies + disables.
   `alembic upgrade head`. Integration test: `relrowsecurity` is true for those tables and the 79
   prior tests still pass. Commit `feat(db): migration 0003 — enable RLS + permissive policies`.
8. **Eval gate (DB-free + manual).** `app/eval/gate.py::check_thresholds(aggregate, thresholds) ->
   (ok: bool, failures: list[str])` (pure); `__main__` runs the harness over the `baseline` config
   with `fake` LLM and exits non-zero on failure. Unit-test pass + fail + boundary. Commit
   `feat(eval): CI eval gate (threshold check)`.
9. **CI/CD (config).** `.github/workflows/ci.yml`: job 1 unit tests (no DB); job 2 spins a
   `pgvector/pgvector:pg16` service, `alembic upgrade head`, runs integration tests with
   `SECOND_BRAIN_LLM_PROVIDER=fake`; job 3 runs `python -m app.eval.gate` (the quality gate). Verify
   YAML parses. Commit `ci: eval-gated test pipeline (unit + integration + quality gate)`.
10. **Deploy + observability artifacts (config).** `deploy/` — `Dockerfile.backend`,
    `Dockerfile.frontend`, `docker-compose.prod.yml` (db + pgbouncer + redis + api + frontend +
    prometheus + grafana), `pgbouncer.ini`, `prometheus.yml` + `alerts.yml` (latency/error/up alerts),
    grafana provisioning + one dashboard JSON, `.env.prod.example`. Verify `docker compose -f
    deploy/docker-compose.prod.yml config` parses. Commit `feat(deploy): prod compose + pgbouncer +
    prometheus/grafana`.
11. **Query-optimization pass (DB-bound, doc).** Run `EXPLAIN (ANALYZE, BUFFERS)` on the vector and
    full-text candidate queries; capture index-on vs `enable_indexscan=off`/`SET hnsw.ef_search`
    contrasts; write `docs/query-optimization.md` with the before/after and the takeaway. Commit
    `docs: query-optimization EXPLAIN ANALYZE before/after`.
12. **ADRs + runbooks + docs (DB-free).** ADR-0011 (VPS), ADR-0012 (productionization + governance);
    index them. `docs/runbooks/{deploy-checklist,backup-restore,incident-response}.md`. README Phase 6
    run/verify. Flip PROGRESS Phase 6 → ✅ with a dated entry; record off-spec calls in
    implementation-notes. Commit `docs: phase-6 ADRs + runbooks + run/verify + progress`.

## Self-review (against project-plan Phase 6 + JD)
- Deploy Docker Compose to VPS → Task 10 (compose.prod + Dockerfiles) + deploy runbook (Task 12); live deploy deferred ✅
- CI/CD with eval gate → Tasks 8, 9 ✅
- Prometheus/Grafana + alerting + runbooks → Tasks 6, 10, 12 ✅
- RLS + audit log → Tasks 2, 7 ✅
- Retention TTL + delete-my-data path → Tasks 3, 4, 5 ✅
- PgBouncer pooling → Task 10 ✅
- Backup/restore runbook → Task 12 ✅
- Query-optimization before/after → Task 11 ✅
- Tests alongside code (unit + integration vs real Postgres) → every code task ✅
- $0 / no recurring bill beyond the one VPS (ADR-0011 picks the $0/cheap box; CI on free minutes) ✅

## Known sharp edges (flagged, not placeholders)
1. **RLS must not break the app.** The app connects as the table **owner** (`second_brain`), which
   bypasses RLS; the permissive `USING (true)` policy covers any non-owner path. Do NOT `FORCE ROW
   LEVEL SECURITY` (would break owner access). Confirm all 79 tests stay green after 0003.
2. **Audit txn ownership.** `audit.record` flushes but does not commit — the calling service/endpoint
   owns the transaction so an audit row and its action commit atomically (and roll back together in
   tests). The `db_session` fixture rolls back, so audit rows never leak between tests.
3. **Metrics path label cardinality.** Label requests by **route template** (`/data/sources/{id}`),
   not the raw path, or per-id paths explode the series. Pull the template from the matched route.
4. **`/metrics` must be exempt from auth and cheap.** No DB hit; expose process + app counters only.
5. **CI service-container DSN.** GitHub's `postgres` service is reachable at `localhost:5432` inside
   the job — set `SECOND_BRAIN_TEST_DATABASE_URL` to the pgvector service, and wait on its healthcheck
   before `alembic upgrade head`.
6. **Compose prod is lint-only in CI.** Never `up` the prod stack in CI; `docker compose config`
   validates it. The dev `docker-compose.yml` stays db-only and untouched.
