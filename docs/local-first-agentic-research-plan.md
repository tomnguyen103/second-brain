# Local-First Agentic Research Plan

## Summary

Second Brain pivots from a VPS-hosted personal memory store to a local-first research
cockpit:

```text
Obsidian = source of truth
NotebookLM = manual deep research lab
Agents/MCP = controlled workflow layer
Local Postgres = rebuildable search index
VPS = demo/portfolio environment only
```

The existing FastAPI, pgvector, hybrid retrieval, eval, MCP, and deployment work stays
valuable. The change is ownership: private knowledge lives as Markdown in Obsidian, while
Postgres stores derived chunks and embeddings that can be rebuilt from the vault.

## Architecture

- **Canonical memory:** `C:\Users\huuth\Documents\SecondBrainVault`, local-only in v1.
- **Derived index:** local Postgres + pgvector/full-text, rebuilt from vault Markdown files. The
  daily default excludes `.obsidian/`, `Templates/`, and `90 Archive/` from indexing; include/exclude
  behavior is configurable.
- **Agent interface:** local stdio MCP tools with approval gates.
- **Research workflow:** NotebookLM remains manual. Agents help prepare, clean, structure, and
  save outputs, but do not automate NotebookLM.
- **VPS:** sanitized demo corpus, public screenshots, HTTPS, CI/CD, monitoring, and portfolio
  proof. It must not be the durable home for private research.

## Cost Model

- Local vault: free.
- Local Postgres index: free on the workstation.
- NotebookLM and coding agents: use existing subscriptions/manual workflows.
- Sync: local-only in v1; Obsidian Sync or Git sync are explicit future choices.
- VPS: keep the smallest useful demo box. Do not scale VPS resources for private memory.
- Managed vector stores, cloud tracing, managed Kubernetes, and always-on paid agent services are
  out of scope unless explicitly approved.

## Security Model

- All vault file access is restricted to the configured vault root.
- Indexing reports status before/after work with `vault_status`; `reindex_vault` reports requested,
  indexed, skipped, removed stale, and excluded counts.
- MCP write/delete/purge-style actions require explicit approval.
- Generated notes must be source-aware and labeled as derived when based on NotebookLM output.
- Agent traces, approval records, and audit logs stay local by default.
- No raw secrets, API keys, credentials, or hidden reasoning should be written to the vault.
- VPS export/purge is a gated runbook: export and verify local Markdown before deleting anything.

## Multi-Agent Roles

- **Triage Agent:** classify the user request as quick answer, research, note creation, or action.
- **Research Planner Agent:** propose source questions and NotebookLM prompts.
- **Synthesis Agent:** turn selected source material into durable Markdown.
- **Vault Curator Agent:** choose folder, title, tags, links, and related notes.
- **Security/Privacy Agent:** check data movement, prompt injection risk, and secrets.
- **Indexer Agent:** refresh the derived local search index from Obsidian.

These roles are workflow responsibilities, not unlimited autonomous workers. v1 keeps human
approval in front of every durable write.

## Daily Workflow

1. User asks a question or pastes source text.
2. Agents classify whether deep research is needed.
3. For deep work, agents prepare a research brief and NotebookLM questions.
4. User performs NotebookLM study manually with selected sources.
5. User pastes or exports useful NotebookLM output.
6. Agents synthesize a clean Markdown note.
7. User approves the write.
8. Note is saved to Obsidian.
9. Agent checks `vault_status`, reindexes the saved note or vault, then checks/searches again.
10. Future chats/searches retrieve from the cleaner vault-derived index.

## Implementation Phases

### Phase L0 - Documentation And Vault

- Add this plan and ADR-0015.
- Create the local vault folder structure.
- Keep the vault local-only.

### Phase L1 - Vault Indexing

- Add `SECOND_BRAIN_VAULT_PATH`.
- Add configurable include/exclude behavior for vault indexing.
- Parse Markdown files from the vault.
- Index them into local Postgres using the existing chunking, embedding, and hybrid retrieval path.
- Exclude noisy daily-use folders by default: `.obsidian/`, `Templates/`, and `90 Archive/`.
- Treat the index as disposable and rebuildable.

### Phase L2 - Approval-Gated MCP Tools

- Add local tools for vault search, read, proposed writes, research-note creation, NotebookLM
  capture, and reindex.
- Add `vault_status` as a direct read-only status check for vault/index health and pending approvals.
- Restrict all paths to the vault root.
- Require approval before writes.

### Phase L3 - Export/Purge Runbook

- Export keeper notes from app/VPS DB to Markdown.
- Verify local Markdown count and contents.
- Purge personal data from VPS only after verification.
- Seed sanitized demo data for portfolio use.
- Follow `docs/runbooks/local-first-export-purge.md`.

### Phase L4 - Agent Workflow Upgrade

- Evaluate LangGraph vs OpenAI Agents SDK.
- Default to LangGraph on tie because it fits explicit local workflows, persistence, and
  human approval checkpoints.
- Keep traces/checkpoints local by default.

## Acceptance Criteria

- Obsidian vault exists locally with the approved folder structure.
- ADR-0015 states Obsidian is canonical memory.
- Markdown notes can be indexed into local Postgres and found by hybrid search.
- Default indexing avoids `.obsidian/`, `Templates/`, and `90 Archive/` unless explicitly
  reconfigured.
- `vault_status` gives a simple before/after status view for daily indexing.
- MCP tools cannot access paths outside the vault.
- MCP writes are approval-gated.
- VPS is documented as demo-only for private data.
