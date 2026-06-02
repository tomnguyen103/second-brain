# ADR-0010 — MCP server + agentic actions

- **Status:** Accepted
- **Date:** 2026-06-02
- **Deciders:** project owner (accepted at recommended defaults under the `/goal` directive)
- **Context phase:** Phase 4 (MCP server + agentic actions)

## Context

AGENTS.md locks the agent tooling to an **MCP server**. Phase 4 exposes the assistant's
capabilities as MCP tools an external client (Claude Desktop, the `mcp` Inspector) can call:
**search**, **create task**, **send digest**, and the flagship **research-this-topic** (the app
researches a topic and files the result back into the brain). The work must reuse the Phase 1
seams (retrieval, ingest, `LLMClient`), stay testable without the stdio transport, cost `$0`, and
run inline/synchronous (ADR-0007).

## Decision

**SDK + transport.** The official Python MCP SDK (`mcp`, `FastMCP`), **stdio** transport, run via
`python -m app.mcp_server`. Tools are declared with `@mcp.tool()`.

**Thin tools over tested services.** All logic lives in services that take a `db` session
(`app/tasks`, `app/digest`, `app/research`, plus the existing `retrieval`); each MCP tool opens its
own `SessionLocal()`, builds the embedder/LLM, calls a service, and returns a JSON-able result.
This keeps the logic unit/integration-testable with the rolled-back `db_session` fixture; the
server module is smoke-tested (imports + `list_tools()` returns the five names).

**The five tools.**
- `search_notes(query, top_k)` — hybrid retrieval over the brain (read-only).
- `create_task(title, detail)` / `list_tasks(status, limit)` — a new **`tasks` table**
  (migration `0002`); a user task is distinct from a pipeline `Job` (ADR-0004).
- `send_digest(limit)` — composes a markdown digest of recent activity (counts + recently added
  documents). Composes only; delivery (email/transport) is Phase 5/6.
- `research_topic(topic)` — the flagship: the LLM writes a research note, which is stored as a
  **`research_note`** source and run through the normal ingest pipeline (chunk + embed), so it
  becomes permanently searchable. Inline (not queued); the `research` job type is reserved for the
  async path in Phase 5. Research uses the configured `LLMClient` (Gemini default, Ollama "private
  mode", `fake` for tests) — not Gemini-only; only the optional external **web search** is deferred.

**Provider + determinism.** Tools use the configured `LLMClient` (Gemini default). For tests and a
keyless smoke, `SECOND_BRAIN_LLM_PROVIDER=fake` makes `research_topic` deterministic; the note is
still stored, embedded, and searchable.

## Consequences

- **Good:** every Phase 4 / JD agentic bullet has a concrete home (tool-use over MCP; the
  research tool closes the loop research → store → auto-ingest → searchable). Migration `0002`
  exercises schema versioning. Verified: 78 tests pass; a live smoke ran `search_notes`
  (top hit "HNSW index tuning") and `send_digest` against the real DB.
- **Good:** the thin-tool/fat-service split means the protocol layer is trivial and everything
  underneath is covered by unit/integration tests.
- **Cost:** `research_topic` runs the LLM inline, so a real (Gemini) research call blocks its tool
  invocation. Fine for one user; the `jobs` table is the async escape hatch (Phase 5).
- **Constraint:** a tool that writes (`create_task`, `research_topic`) commits to the DB; tests use
  the services (rolled-back fixture), not the tools, to stay isolated.

## Alternatives considered

- **HTTP/SSE transport instead of stdio.** Useful for remote clients, but stdio is the standard
  local-client path (Claude Desktop) and the simplest to run/test. SSE can be added later
  (`FastMCP` supports it) without touching the tools.
- **Overload the `jobs` table for tasks.** Its type CHECK is pipeline-only (`ingest|embed|briefing|
  research`); a user to-do is a different concept. A dedicated `tasks` table is the honest model.
- **Store research notes as documents under an existing source.** Muddies retrieval provenance;
  a dedicated `research_note` source (already an allowed `sources.type`) keeps automated research
  identifiable and filterable.
- **Async research via the `jobs` queue now.** Adds a worker + polling to the MVP of this phase;
  deferred to Phase 5 where scheduled work makes it pay off.
