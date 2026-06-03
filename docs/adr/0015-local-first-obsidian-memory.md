# ADR-0015 - Local-first Obsidian memory

- **Status:** Accepted
- **Date:** 2026-06-03
- **Deciders:** project owner
- **Supersedes / relates:** Supersedes the private-data assumption behind ADR-0011/0012 that the
  VPS/Postgres deployment is the real long-term home for personal memory. The VPS remains the
  production/demo runtime for the portfolio app.

## Context

The project has already proven the full RAG/product/ops stack: FastAPI, Next.js, Postgres +
pgvector, hybrid retrieval, MCP tools, daily briefing, eval gates, Docker Compose, Caddy HTTPS,
and Kubernetes learning evidence.

For daily personal use, however, storing private research, chats, and agent outputs on a VPS is
not the best privacy or cost posture. The owner also uses Obsidian, NotebookLM, Claude/Codex, and
Gemini/Antigravity manually. These tools point to a better architecture: keep durable knowledge as
local Markdown, use NotebookLM as a manual research room, and let agents operate through guarded
local tools.

## Decision

**Obsidian Markdown is the canonical memory for private knowledge.** The default vault path is
`C:\Users\huuth\Documents\SecondBrainVault`. Research notes, selected agent outputs, decisions,
source digests, and NotebookLM captures should be saved there.

**Postgres is a derived local index/cache for private knowledge.** The existing pgvector/full-text
retrieval stack stays, but for personal data it must be rebuildable from the Obsidian vault. Vault
paths and file metadata are stored as document metadata/external ids rather than becoming the
source of truth.

**Vault indexing has daily-use safety defaults.** Full-vault indexing excludes `.obsidian/`,
`Templates/`, and `90 Archive/` by default to avoid Obsidian config, templates, and archived clutter
showing up in everyday search. Include/exclude behavior is configurable via
`SECOND_BRAIN_VAULT_INDEX_INCLUDE_DIRS` and `SECOND_BRAIN_VAULT_INDEX_EXCLUDE_DIRS`; selected
reindex requests fail clearly if they target a configured-excluded path.

**NotebookLM remains manual.** The app will not depend on NotebookLM automation. Agents can prepare
research briefs and clean pasted NotebookLM outputs, but the human chooses sources and decides what
is worth saving.

**Agents operate through local, approval-gated MCP tools.** Read/search/index/write capabilities are
exposed over stdio MCP for Claude/Codex. File operations are constrained to the vault root. Durable
writes require approval.

**Vault status is a read-only daily check.** `vault_status` reports the configured vault path,
whether the vault exists, whether the derived indexed source exists, indexed document count, pending
approval count, Markdown eligible/excluded counts, and active indexing config. Approved
`reindex_vault` results report `requested`, `indexed`, `skipped`, `removed_stale`, and `excluded`.

**The VPS becomes demo/portfolio only for private data.** The existing deployment remains valuable
for screenshots, CI/CD, monitoring, and operational proof. Personal data should be exported,
verified locally, and then purged before the VPS is treated as a demo environment.

## Consequences

- **Good:** private memory is local, inspectable, portable Markdown.
- **Good:** the existing RAG and eval work is preserved as a rebuildable index over real notes.
- **Good:** daily searches avoid noisy Obsidian/config/template/archive folders by default.
- **Good:** cost stays bounded; the VPS no longer needs to grow with the user's private corpus.
- **Good:** NotebookLM is used where it is strongest without adding brittle unofficial integration.
- **Constraint:** archived notes are not indexed by default; opt them in by changing the local
  include/exclude configuration when needed.
- **Constraint:** the local machine becomes the primary daily-use runtime for private knowledge.
- **Constraint:** sync is intentionally deferred; v1 is local-only.
- **Constraint:** export/purge of existing VPS data is a gated runbook, not an automatic job.

## Alternatives considered

- **Keep VPS/Postgres canonical.** Simpler because the app already works, but worse for privacy and
  unnecessary for a single-user private knowledge base.
- **Make NotebookLM canonical.** NotebookLM is excellent for bounded source study, but it is not a
  local plain-text source of truth and should not own the durable memory layer.
- **Build an Obsidian plugin first.** More native UI, but adds plugin complexity before the core
  source-of-truth and indexing model is stable. Direct file access is the v1 foundation.
- **Use a managed vector database.** Adds recurring cost and external data exposure without a clear
  benefit for a local-first personal system.
