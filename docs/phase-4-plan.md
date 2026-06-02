# Phase 4 — MCP server + agentic actions Implementation Plan

> Work TDD (red → green → commit), DRY, YAGNI. Pure logic is DB-free unit-tested; services are
> integration-tested vs real Postgres; the MCP layer stays thin and is smoke-tested.

**Goal:** Expose the assistant's capabilities as tools over an **MCP server** (the locked agent-tooling
choice, AGENTS.md), so an MCP client (Claude Desktop, `mcp` Inspector) can call them. Tools:
**search** (hybrid retrieval over the brain), **create_task** / **list_tasks** (agentic "add to my
tasks"), **send_digest** (compose a digest of recent activity), and the flagship **research_topic**
(LLM researches a topic → stored as a `research_note` source → auto-ingested → permanently searchable).

**Architecture:** the official Python MCP SDK (`mcp` 1.27, `FastMCP`), stdio transport. Heavy logic
lives in **services that take a `db` session** (testable with the rolled-back `db_session` fixture);
the MCP tools are thin wrappers that open `SessionLocal()`, build the embedder/LLM, call a service, and
return a structured result. Reuses Phase 1 seams: `hybrid_search`, `ingest_documents`, `LLMClient`.
Everything inline + synchronous (matches ADR-0007); `fake` LLM for deterministic tests.

**Tech delta:** `mcp>=1.2,<2` (validated install = 1.27.2). New migration `0002` for a `tasks` table.

## Decisions (recommended defaults, revisable)
- **D1 — `tasks` is a new table (migration 0002).** "create task" is a first-class agentic action; a
  small `tasks(id, title, detail, status, created_at)` table is the honest model and exercises Alembic
  (a JD bullet). *Rejected:* overloading `jobs` (its type CHECK is pipeline-only) or storing tasks as
  documents (muddies retrieval).
- **D2 — `research_topic` is inline and stores a `research_note` source.** Generate a summary via
  `LLMClient` → `ingest_documents(source=research_note, doc)` → chunk+embed → searchable. `sources.type`
  already allows `research_note`. *Gave up:* async via the `jobs` table (`research` type exists) — Phase 5,
  where scheduled work pays off. Optional web search is deferred (Gemini-only research in v1).
- **D3 — `send_digest` composes, doesn't email.** It builds a markdown digest of recent sources/documents
  (+ counts) and returns it. Real delivery (email/transport) is Phase 5/6. Honest: "digest" = recent-activity summary.
- **D4 — MCP tools are thin; services hold logic.** Keeps everything unit/integration-testable without the
  stdio transport; the server module is smoke-tested (imports + registers the expected tool names).
- **D5 — `fake` LLM for tests.** `research_topic` with the fake driver yields a deterministic canned
  summary (still ingested + searchable); the real research needs a Gemini key. Mirrors ADR-0001/0008.

## File structure
```text
backend/
  requirements.txt                 # MODIFY: add mcp
  migrations/versions/0002_tasks.py  # CREATE: tasks table
  app/
    db/models.py                   # MODIFY: Task model
    tasks/__init__.py  tasks/service.py     # CREATE: create_task / list_tasks
    research/__init__.py research/service.py # CREATE: research_topic (+ pure prompt helper)
    digest/__init__.py  digest/service.py    # CREATE: build_digest (+ pure formatter)
    mcp_server.py                  # CREATE: FastMCP server, 5 tools, stdio entrypoint
  tests/
    unit/test_research_prompt.py   # CREATE: pure research prompt/format
    unit/test_digest_format.py     # CREATE: pure digest markdown
    unit/test_mcp_server.py        # CREATE: server imports + registers expected tools
    integration/test_tasks.py      # CREATE: create/list vs DB
    integration/test_research.py   # CREATE: research_topic stores + embeds + is searchable
    integration/test_digest.py     # CREATE: digest reflects recent ingest
docs/
  adr/0010-mcp-server-and-agentic-actions.md  # CREATE
  adr/README.md  PROGRESS.md  implementation-notes.md  # MODIFY
backend/README.md                  # MODIFY: Phase 4 run/verify (run server, mcp inspector)
```

## Tasks (TDD)
1. **Deps + tasks table** — add `mcp` to requirements; migration `0002_tasks` + `Task` ORM model;
   `alembic upgrade head`. Integration test: table exists / round-trips.
2. **Tasks service** — `create_task(db, title, detail=None)`, `list_tasks(db, status=None, limit=20)`.
   Integration test create→list, status filter.
3. **Digest service** — pure `format_digest(generated_at, sources, documents, counts)` (unit) +
   `build_digest(db, *, limit=10)` querying recent sources/documents (integration).
4. **Research service** — pure `build_research_messages(topic)` (unit) + `research_topic(db, embedder,
   llm, topic)`: generate summary → `ingest_documents` as a `research_note` source → return the new
   document id + searchable=True. Integration: after research, `hybrid_search` finds the topic.
5. **MCP server** — `FastMCP("second-brain")` with tools `search_notes`, `create_task`, `list_tasks`,
   `send_digest`, `research_topic`; each opens `SessionLocal()`, builds embedder/llm via `deps`/factory,
   calls the service, returns a JSON-able dict. `python -m app.mcp_server` runs stdio. Smoke test:
   import + `list_tools()` contains the 5 names.
6. **ADR-0010 + docs** — ADR for the MCP design + agentic actions; README Phase 4 run/verify (run the
   server; connect via `mcp dev` Inspector or Claude Desktop config); flip PROGRESS Phase 4 → ✅; notes.

## Self-review (against spec + JD)
- MCP server exposing tools → Task 5 ✅ (tool-use/agentic patterns)
- create task · send digest · search · research-this-topic → Tasks 2,3,4,5 ✅
- research → store as source → auto-ingest → searchable → Task 4 ✅ (pipeline integration)
- migrations/schema versioning → Task 1 (migration 0002) ✅
- tests alongside (unit + integration vs real Postgres) → every task ✅
- $0 / inline / fake-driver CI → D2/D5 ✅
- runnable + documented (run server, connect a client) → Task 6 ✅

## Known sharp edges
1. **Tool DB sessions:** MCP tools open their own `SessionLocal()` and `commit()`; services take `db` so
   tests use the rolled-back fixture. Don't call `SessionLocal` inside services.
2. **research_topic dedupe:** re-researching the same topic hits the `UNIQUE(source_id, content_hash)`
   dedupe → returns the existing doc as duplicate. Surface that, don't crash.
3. **Migration applied live:** Task 1 needs `alembic upgrade head` against the 5433 DB before the tasks
   integration tests pass.
4. **MCP SDK call shape:** verify `FastMCP`, `@mcp.tool()`, and `mcp.list_tools()` against the installed
   1.27.2 at implementation time; isolate any change to `mcp_server.py`.
