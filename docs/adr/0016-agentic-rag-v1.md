# ADR-0016 - Agentic RAG v1 with LangGraph

- **Status:** Accepted
- **Date:** 2026-06-05
- **Deciders:** project owner
- **Context phase:** Post-roadmap retrieval quality upgrade

## Context

Regular chat already uses hybrid retrieval: pgvector semantic search plus PostgreSQL full-text
search, fused with RRF, followed by a strict citation/support validator. The desired improvement is
not a new datastore or autonomous action system. It is a better retrieval loop for harder questions:
break the question into focused searches, merge the evidence, and answer only from cited notes.

The project constraints still apply: local-first runtime, no recurring infrastructure cost, no new
privacy surprise, no automatic writes, and eval-gated rollout.

## Decision

Add an opt-in **agentic RAG** mode using **LangGraph** as a small request-scoped graph:

1. `plan_queries` asks the selected `LLMClient` for 2-4 focused search queries.
2. `retrieve_subqueries` runs existing `hybrid_search` for each subquery with the same source/tag
   filters as regular chat.
3. `select_context` deduplicates chunks, rewards chunks supported by multiple subqueries, and caps
   the final context to `top_k`.
4. `verify_evidence` runs only when no usable evidence was found; it can retry the original user
   wording once or refuse.
5. `answer` reuses the normal prompt/citation contract and the same finalization validator as
   regular chat.

V1 is read-only. It does **not** call MCP mutation tools, create tasks, fetch web pages, or write
research notes. It also does not use LangGraph checkpointing; each graph run lives only for the
request. Durable evidence remains the existing `retrievals` rows on the final assistant message.

The mode is behind two gates:

- API request option: `options.agentic=true`
- Server setting: `SECOND_BRAIN_AGENTIC_RAG_ENABLED=true`

The web UI exposes the toggle only when `NEXT_PUBLIC_AGENTIC_RAG_ENABLED=true`. `/chat/stream`
returns `409` for agentic requests; clients should call non-streaming `/chat` so answer text is
only delivered after citation validation.

Agentic eval configs (`agentic`, `gemini-agentic`) compare this graph against the regular baseline.
The regular RAG path remains the default unless the eval and manual review show a clear quality win.

## Consequences

- **Good:** improves recall for multi-part or vague questions without replacing the proven hybrid
  search implementation.
- **Good:** preserves the `LLMClient` seam. Gemini, Ollama private mode, and the fake test driver
  all run through the same graph.
- **Good:** trace metadata is compact and safe: subqueries, hit counts, selected chunk count,
  fallback/verifier flags, and budget. It does not expose private chain-of-thought.
- **Cost:** agentic mode uses extra LLM calls and multiple search queries per turn. It is opt-in and
  bounded by `SECOND_BRAIN_AGENTIC_RAG_MAX_SUBQUERIES` and the graph recursion limit.
- **Constraint:** v1 does not token-stream answer deltas. This keeps the existing safety posture:
  unvalidated model text is not emitted to the browser.

## Alternatives considered

- **Replace regular RAG outright.** Rejected because the baseline is proven, faster, and easier to
  reason about. Agentic RAG should earn default status through eval.
- **Build a custom loop without LangGraph.** Rejected because the owner explicitly chose LangGraph
  and its graph API gives a clearer future path for human-in-the-loop or async flows.
- **Use LangChain agents or LlamaIndex.** Rejected for v1 because the project already has retrieval,
  prompting, eval, and provider seams. A low-level graph adds less architecture drift.
- **Persist graph state.** Deferred. Checkpointing is useful for long-running or interruptible
  agents, but chat v1 is synchronous and request-scoped.
