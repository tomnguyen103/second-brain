# ADR-0004 — Pipeline trigger: durable `jobs` table + `LISTEN/NOTIFY` wake-up

- **Status:** Accepted
- **Date:** 2026-06-01
- **Deciders:** project owner
- **Context phase:** Phase 0 (schema), used from Phase 1 (ingest) and Phase 5 (briefing)

## Context

Ingest, embedding, briefing, and research run as background work off the request path. We want this without
standing up a separate broker (Redis/RabbitMQ/Celery) — "use the database you already have." The risk with
the lightest option, raw `LISTEN/NOTIFY`, is that notifications are **fire-and-forget**: if no worker is
connected at NOTIFY time (crash, deploy, restart), the event is lost.

## Decision

Model a durable **`jobs` table** (`type`, `payload`, `status`, `attempts`, `last_error`, timestamps) as the
source of truth for background work. Workers claim queued rows (`status='queued'` ordered by
`scheduled_at`, `FOR UPDATE SKIP LOCKED`). Use **`LISTEN/NOTIFY` only as a low-latency wake-up** so idle
workers react instantly instead of polling tightly — but correctness never depends on the notification.

## Consequences

- **Good:** restart-safe and inspectable — a crashed worker leaves a claimable row; `SELECT * FROM jobs
  WHERE status='failed'` is the dead-letter view. Retries via `attempts`/`last_error`. No extra infra.
- **Good:** `NOTIFY` keeps latency low in the happy path without a busy poll loop.
- **Cost:** workers still need a slow fallback poll (e.g. every few seconds) to catch jobs enqueued while
  disconnected. Cheap at single-user scale.
- **Defensible trade-off:** contrasts cleanly with the Redis/queue alternative for the ADR/JD story.

## Alternatives considered

- **`LISTEN/NOTIFY` only:** least infra, lowest latency — but at-most-once delivery loses events across
  restarts. Rejected as the source of truth; kept as the wake-up signal.
- **Redis / Celery broker:** mature, but adds a service, a dependency, and ops surface for work a single
  Postgres table handles fine here. Rejected for now; revisit only if throughput outgrows one box.
