# Implementation Notes — Second Brain

A running record of decisions, changes, and trade-offs that **weren't in the original
spec** — the "why it ended up like this" you'll want when you (or a reviewer) look back.
Append a dated entry whenever you make a non-obvious call during implementation.

How to use: newest entries on top. For each, note **what**, **why**, and **trade-off /
what I gave up**. Keep it honest — the surprises are the valuable part.

---

## Decisions made during planning (before any code)

These shaped the spec itself and are worth recording, since none were in the very first
"build a personal project" brief.

### LLM driver: Gemini Flash API (free tier), not local-only
- **Why:** keeps the VPS tiny and cheap — no GPU, no model resident 24/7, no per-token
  bill. Free tier (~1,500 req/day) is plenty for one user.
- **Trade-off:** query text + retrieved chunks transit to Google (privacy cost; noted for
  the GDPR story). Mitigation: a local Ollama path kept behind the same `LLMClient`
  interface as a "private mode" — flip by config.

### Runtime: Docker Compose on one VPS, NOT Kubernetes
- **Why:** single-user app; K8s's benefits (multi-node, autoscaling, self-healing) solve
  problems we don't have. Managed K8s would blow the ~$5/mo budget to $70+/mo.
- **Trade-off:** no "runs on K8s in prod" claim. Recovered by making K8s a **learning
  track** (Phase 7) on free local k3s/kind — manifests, HPA, ingress, CI/CD proven and
  screenshotted, then torn down. Judgment ("knew when not to use K8s") is itself a signal.

### Database: self-hosted Postgres as the workhorse, not a managed vector DB
- **Why:** one engine does relational + pgvector + full-text + JSONB + analytics; no extra
  managed-service fee or storage cap; richer SQL/modeling story for the JD.
- **Trade-off:** you operate it yourself (backups, pooling, tuning) — but that's the point
  for the "I can operate Postgres" signal. Redis kept only for caching/rate-limit.

### Research flow: app does its own research; NotebookLM stays manual
- **Why:** Gemini chats emit no events to hook, and NotebookLM has no free API — a
  programmatic chain would be brittle. An in-app "research this topic" MCP tool (Gemini +
  optional web search → summarize → store → auto-ingest) is robust and controllable.
- **Trade-off:** no automatic Gemini-chat → NotebookLM → brain pipe. NotebookLM is used by
  hand for deep study; you paste anything worth keeping into the app's capture path.

### Gemini Ultra subscription ≠ API quota
- **Clarification (not a choice):** the Ultra subscription powers the consumer apps
  (NotebookLM, Gemini app, Antigravity) used by hand; the app's code uses the separate
  free Gemini **API** tier. Don't expect Ultra to raise the API limits.

---

## Implementation-time notes

### 2026-06-01 — Phase 0 closed under `/goal end of phase 0` (decisions LOCKED)
The session goal directive said to drive Phase 0 to completion without pausing, so the 5 proposals
below were **accepted at their recommended defaults** rather than waiting for interactive sign-off,
and each is now an ADR (`docs/adr/0002–0004`; D4/D5 captured in the ER doc + this note). If you'd
have chosen differently on any, say so and I'll revise the ADR + migration before Phase 1 builds on it.

Two implementation-time deviations worth recording:
- **Requirements are version *ranges*, not hard pins.** Why: this machine runs Python 3.14 and the
  originally pinned `psycopg-binary==3.2.1` has no 3.14 wheel. Ranges (`alembic>=1.13.2,<2`,
  `SQLAlchemy>=2.0.31,<2.1`, `psycopg[binary]>=3.2.10,<3.4`, `pgvector>=0.3.2,<0.5`,
  `pydantic-settings>=2.3.4,<3`) resolve across 3.11–3.14. *Gave up:* exact reproducibility — re-pin
  to a lockfile once the VPS Python is fixed in Phase 6.
- **Live migration not applied in this environment.** Docker isn't installed on this box, so Phase 0
  was verified *offline*: models import (12 tables on metadata) + `alembic upgrade head --sql` renders
  full DDL. The live `alembic upgrade head` against pgvector is a documented user step
  (backend/README). *Gave up:* an end-to-end "rows in a real DB" proof until Docker is available.

The five schema-shaping calls (now locked):
- **Embeddings as a separate table, `vector(384)`, one model** — keeps re-embedding additive
  (pgvector dims are fixed). *Gave up:* the simplicity of a single `chunks.embedding` column.
- **Chunking ~512 tokens / ~15% overlap, semantic-boundary split** — safe MiniLM-class default.
  *Gave up:* nothing yet; just needs your target size confirmed before ADR-0003.
- **`jobs` table + LISTEN/NOTIFY as wake-up** (not NOTIFY-only) — durable, restart-safe.
  *Gave up:* a bit more infra than pure NOTIFY, in exchange for not losing events.
- **`bigint` identity keys** (not uuid) — smaller/faster for a single-user app.
  *Gave up:* client-generated IDs / row-count opacity (don't need either here).
- **`raw_text` purged after embedding** — supports the retention / delete-my-data story.
  *Gave up:* keeping the original blob around for cheap re-chunking later.
- Affects: Phase 0 migrations, future ADR-0002/0003/0004.

*(Implementation-time notes — newest on top. Template below.)*

<!--
### YYYY-MM-DD — <short title>
- What: 
- Why: 
- Trade-off / what I gave up: 
- Affects: <files / phases>
-->
