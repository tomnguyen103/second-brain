# ADR-0012 — Productionization + data governance

- **Status:** Accepted
- **Date:** 2026-06-02
- **Deciders:** project owner (accepted at recommended defaults under the `/goal` directive)
- **Context phase:** Phase 6 (productionize + data-ops hardening)

> **Runtime update 2026-06-05:** ADR-0015 changes the default runtime to local-first Docker
> Compose. The governance, CI, metrics, runbook, and optional deploy artifacts in this ADR remain
> accepted; the VPS is no longer required for daily use.

## Context

Phase 6 turns the working app into something operable and governable: data governance
(RLS, audit, retention, GDPR access/erasure), connection pooling, observability + alerting,
an eval-gated CI/CD pipeline, and ops docs. All of it must be code/config that builds and
tests **without** a purchased server, stay `$0` in CI (free minutes, fake LLM), and not break the
existing suite.

## Decision

**Audit = app-layer service, not DB triggers (D2).** Governed actions call
`app/dataops/audit.record(...)`, which writes an `audit_log` row in the caller's transaction
(flush, no commit). Explicit about actor/action/entity, portable, unit/integration-testable.
Acceptable for a single-user app where all writes go through the API/services.

**RLS enabled with a permissive `USING (true)` policy (D3, migration `0003`).** Demonstrates
the governance mechanism + migration discipline without breaking the single-role app: the app
connects as the table **owner** (bypasses RLS) and the permissive policy covers any non-owner
role (e.g. a future least-privilege app role behind PgBouncer). We do **not** `FORCE` RLS. The
policy predicate is the documented seam for real per-tenant scoping if the app goes multi-user.

**Retention nulls `documents.raw_text` after embedding + TTL (D4).** `raw_text` is the original
full-document copy retained for debugging/export while fresh; `purge_raw_text(older_than_days)`
nulls it for embedded docs past the TTL (`retention_raw_text_days`, default 180). Chunks and
embeddings stay because they are the retrieval units, so retention reduces duplicate raw-source
storage but is not anonymization. Erasure is the separate source-delete path. Citation rendering
already tolerates a purged source.

**Delete-my-data = source-level erasure with FK cascade (D5).** `delete_source` issues a Core
`DELETE` so the DB's `ON DELETE CASCADE` removes documents → chunks → embeddings (the ORM has no
delete-cascade rule and would try to NULL the NOT NULL FK). `export_source` returns the same
subtree as JSON first (right-to-access). Both audited. A `source` is the unit the user added,
so it's the natural ownership granularity.

**Admin endpoints behind a bearer token.** `require_admin` returns 503 when no
`SECOND_BRAIN_ADMIN_TOKEN` is set (feature off by default) and 401 on a wrong/missing token.
Guards `GET /data/export`, `DELETE /data/sources/{id}`, `POST /admin/retention/purge`.

**Observability = Prometheus + Grafana, self-hosted.** A dedicated `CollectorRegistry`,
request middleware labelling by **route template** (not raw path, to bound cardinality), and a
`/metrics` endpoint. Compose adds Prometheus (scrape + alert rules) and Grafana (provisioned
datasource + dashboard).

**CI eval gate on LLM-independent metrics (D6).** `app/eval/gate.py` runs the eval set on the
deterministic `baseline` config (fake LLM, keyless) and fails the build if `hit_at_k`,
`citation_validity`, or `refusal_accuracy` regress below threshold. Answer-text quality needs
the real `gemini` run and stays a manual step (ADR-0008).

**PgBouncer in session pooling mode (D7).** Session mode keeps psycopg3 prepared statements
working; transaction mode would require `prepare_threshold=None`. Migrations run against the DB
directly (not through the pooler). `docker-compose.prod.yml` is additive and never run in CI
(`docker compose config` lints it); the dev `docker-compose.yml` stays db-only.

## Consequences

- **Good:** every Phase 6 / JD bullet has a concrete home — RLS + audit + retention +
  GDPR delete/export (data governance), Prometheus/Grafana + alerts (monitoring), eval-gated
  GitHub Actions (MLOps CI/CD), PgBouncer (pooling), query-tuning before/after
  (`docs/query-optimization.md`). Verified: 114 tests pass; RLS does not break owner access.
- **Good:** secrets stay out of git — only `*.example` templates are committed; real
  `deploy/.env.prod` and `deploy/pgbouncer/userlist.txt` are gitignored.
- **Constraint:** admin endpoints are off until a token is set (safe default for a single-user
  box). RLS is permissive (no second tenant to scope against yet).
- **Deferred:** optional VPS/cloud deploy; transaction-mode pooling; remote MLflow; LLM-as-judge
  eval. Frontend currently served via `npm start` in its image (standalone-output optimization
  left for later given the Next 16 breaking changes).

## Alternatives considered

- **DB triggers for audit.** Captures out-of-band SQL too, but is harder to test and less
  portable; all writes go through services here, so app-layer auditing is sufficient and clearer.
- **FORCE RLS with real row scoping now.** No second user to scope against; forcing it would
  break owner access and the suite for zero governance gain today. Permissive policy + documented
  seam is the honest middle.
- **Hard-delete chunks on retention TTL.** Would break search; retention only nulls the original
  `documents.raw_text` copy, erasure (a separate path) removes the source subtree.
- **Gate CI on answer-text quality.** Needs the real Gemini run (non-deterministic, keyed,
  costs quota) — unfit for CI; gated metrics are the LLM-independent ones.
- **Exercise the full prod stack in CI.** Too heavy; `docker compose config` lint + the deploy
  runbook cover it, and the eval gate already runs the real pipeline against a pgvector service.
