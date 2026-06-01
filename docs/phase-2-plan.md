# Phase 2 — Readiness & Plan (Next.js chat UI)

> **Status: PREP / DRAFT — not started.** This doc exists so Phase 2 can begin cleanly the
> moment Phase 1's API is running. It is the handoff between the frozen Phase 1 contracts
> (ADR-0007) and the frontend. Review and refine at Phase 2 kickoff; the open decisions at the
> bottom are deliberately left for then.

**Goal (from the roadmap):** a daily-usable Next.js + TypeScript chat UI over the Phase 1
backend — streaming responses, source **citations**, and semantic **search**. This is the
primary screenshot-able surface (LinkedIn/Instagram).

**Depends on:** Phase 1 `/ingest`, `/chat`, `/health` live (ADR-0007). CORS for
`http://localhost:3000` is already enabled by the Phase 1 backend (`main.py`).

---

## What Phase 2 consumes (the contract → TypeScript)

The frozen `/chat` and `/ingest` shapes (ADR-0007) map directly to TS types. Generate or
hand-write these in `frontend/lib/api/types.ts`:

```typescript
export interface ChatRequest {
  message: string;
  conversation_id?: number | null;
  top_k?: number;
  filters?: { source_ids?: number[]; tags?: string[] };
  options?: { private_mode?: boolean; include_chunks?: boolean };
}

export interface Citation {
  marker: number;
  chunk_id: number;
  document_id: number;
  document_title: string;
  source_id: number;
  source_name: string;
  snippet?: string | null;
  score: number | null;
  vector_score: number | null;
  fulltext_score: number | null;
  method: "vector" | "fulltext" | "hybrid";
  char_start?: number | null;
  char_end?: number | null;
}

export interface ChatResponse {
  conversation_id: number;
  message_id: number;
  answer: string;
  citations: Citation[];
  usage: { prompt_tokens: number | null; completion_tokens: number | null; total_tokens: number | null };
  model: string | null;
  latency_ms: number;
  retrieval: { method: string; candidates_vector: number; candidates_fulltext: number; fused_returned: number };
}
```

> **Tip:** to keep these in lockstep with the backend, serve FastAPI's OpenAPI schema
> (`/openapi.json`) and generate types with `openapi-typescript` in a small npm script, rather
> than hand-maintaining them. Decide at kickoff (see open decisions).

---

## Proposed structure (App Router)

```
frontend/
  app/
    layout.tsx
    page.tsx                  # redirect → /chat
    chat/page.tsx             # main chat surface
    search/page.tsx           # semantic search results
  components/
    ChatComposer.tsx          # input + send (+ private-mode toggle)
    MessageList.tsx           # user/assistant turns
    AnswerWithCitations.tsx   # renders answer, turns [n] into clickable refs
    CitationCard.tsx          # source/doc/snippet on hover/click
    SourceFilter.tsx          # filter by source_ids / tags
    SearchBar.tsx / ResultList.tsx
  lib/
    api/client.ts             # typed fetch wrapper (base URL from env)
    api/types.ts              # the interfaces above
  .env.local                  # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

**Citation UX:** parse `[n]` markers in `answer`, map to `citations[]` by `marker`, render each
as a superscript link that opens a `CitationCard` (source name · doc title · snippet · the
char span). This is the "explainability" visual the JD rewards.

---

## Backend deltas Phase 2 will likely need (new Phase 2 tasks, not Phase 1)

These are **out of Phase 1 scope** — listed here so they're not a surprise:

| Need | Endpoint (proposed) | Notes |
|---|---|---|
| Render chat history | `GET /conversations`, `GET /conversations/{id}` | reads `conversations`/`messages`/`retrievals` |
| Semantic search page | `GET /search?q=&top_k=&source_ids=` | thin wrapper over `retrieval.hybrid_search` (already built in Phase 1) |
| Thumbs up/down | `POST /feedback` | writes the `feedback` table (schema exists) |
| Streaming answers | `POST /chat/stream` (SSE) | **deferred** — Phase 1 is non-streaming (ADR-0007); add here if we want token streaming |

`/search` is cheap because `hybrid_search` already exists from Phase 1 Task 10 — it's mostly a
new router + schema.

---

## Open decisions (resolve at Phase 2 kickoff)

1. **Streaming**: ship non-streaming first (reuse `/chat` as-is) and add SSE later, or build
   `/chat/stream` from the start? (Recommend: non-streaming first — fastest to a screenshot.)
2. **Type sync**: `openapi-typescript` codegen vs hand-written `types.ts`. (Recommend codegen.)
3. **Data/state**: TanStack Query vs SWR vs plain fetch + React state. (Recommend TanStack Query.)
4. **Styling**: Tailwind vs CSS modules vs a component lib (shadcn/ui). (Recommend Tailwind +
   shadcn/ui for speed + clean screenshots.)
5. **Auth**: single-user app → no auth initially; revisit only if deployed publicly in Phase 6.
6. **Frontend hosting (cost!)**: Vercel free tier vs static export served from the same VPS.
   Per AGENTS.md cost rules, **flag before choosing anything with a recurring bill** — Vercel's
   free tier is $0 for personal use; the VPS-served option keeps everything on the one box.

---

## Definition of done (Phase 2)

- `npm run dev` serves a chat page that calls the live Phase 1 `/chat` and renders a cited
  answer with working `[n]` → source cards.
- A search page returns ranked results from `/search`.
- Source/tag filters drive `filters` on `/chat` and `/search`.
- A clean demo screenshot for LinkedIn/Instagram.
- Deferred to later phases: streaming polish (or done here if decision #1 says so), feedback
  analytics dashboards (Phase 3/6), auth/deploy (Phase 6).
