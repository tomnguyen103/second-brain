# ADR 0015: Local-first Obsidian memory with a manual NotebookLM bridge

- **Status:** Accepted
- **Date:** 2026-06-03
- **Context phase:** Post-roadmap workflow hardening

## Context

Second Brain is live as a RAG assistant with `/ingest`, `/chat`, `/search`, daily briefings,
and MCP research tools. The owner also uses NotebookLM manually for deep study. NotebookLM has
no supported free programmatic API, and the project already decided not to automate it.

The missing piece is a repeatable daily workflow: ask a question, decide whether NotebookLM is
needed, use NotebookLM by hand when it is useful, keep only reviewed Markdown in Obsidian, then
reindex and verify retrieval.

## Decision

Obsidian is the local-first staging and approval surface for NotebookLM-derived memory.

- NotebookLM remains manual. No browser automation, unofficial API wrapper, or transcript scraper.
- Raw NotebookLM transcripts are not saved by default.
- The vault stores reviewed notes with explicit provenance frontmatter: `title`, `kind`,
  `status`, `created`, `derived`, `source_tool`, and `tags`.
- The normal note types are `research-brief`, `notebooklm-session`, and `source-digest`.
- Only approved Markdown is sent back through the normal Second Brain ingest path.
- Every keeper note should be search-verified after reindexing.

## Consequences

- Provenance is clear: the app can distinguish manual notes, NotebookLM-derived notes, and agent
  outputs by frontmatter and source metadata.
- The workflow protects privacy and quality by keeping a human approval gate before ingest.
- The trade-off is explicit friction: a person must decide what is worth saving and run the
  reindex step.
- NotebookLM output can still improve the brain, but NotebookLM itself is not part of the app's
  automated system boundary.

## Alternatives Rejected

- **Automate NotebookLM with browser control or unofficial APIs.** Too brittle and outside the
  supported product boundary.
- **Save raw transcripts by default.** High noise, weak provenance, and worse privacy posture.
- **Paste NotebookLM output straight into `/ingest`.** Faster, but skips the review and cleanup step.
- **Make NotebookLM the source of truth.** It is useful for study, but Obsidian plus Postgres remain
  the durable local memory path.
