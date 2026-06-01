# ADR-0001 — LLM driver: hosted Gemini Flash default, local Ollama behind one interface

- **Status:** Accepted
- **Date:** 2026-06-01
- **Deciders:** project owner
- **Context phase:** Phase 0 (formalizes a decision already fixed in the spec)

## Context

The assistant needs an LLM for generation (RAG answers, briefing summaries, research). The runtime
budget is one small VPS (~$4–6/mo) with no GPU. Two pressures pull against each other: keeping the box
tiny/cheap, and keeping private data off third-party servers.

## Decision

Default generation runs on the **hosted Gemini Flash API (free tier, ~1,500 req/day)**. All model calls
go through a single `LLMClient` interface. A **local Ollama** driver implements the same interface as a
"private mode," selectable by config — no code changes to swap.

Embeddings are unaffected by this ADR: they run **locally** (sentence-transformers) on ingest only.

## Consequences

- **Good:** VPS stays tiny — no resident model, no GPU, no per-token bill. The interface seam is itself a
  strong engineering signal (swap providers by config) and maps to the JD's "LLM integration" bullet.
- **Cost:** query text + retrieved chunks transit to Google on the default path. This is the documented
  privacy trade-off for the GDPR story; the Ollama path is the mitigation (fully local, no external calls).
- **Constraint:** any provider-specific feature must be hidden behind `LLMClient`; nothing above the
  interface may assume Gemini.

## Alternatives considered

- **Local-only LLM:** maximal privacy, but needs real RAM/CPU or a GPU resident 24/7 — breaks the budget.
- **Hosted-only (no Ollama path):** simpler, but gives up the private mode and the abstraction story.
