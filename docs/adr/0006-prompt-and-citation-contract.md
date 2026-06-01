# ADR-0006 — Prompt template, citation contract, and grounding policy

- **Status:** Accepted
- **Date:** 2026-06-01
- **Deciders:** project owner
- **Context phase:** Phase 1 (`/chat` generation)

## Context

RAG answers must be grounded in the retrieved chunks and must cite them — for trust, and for
the JD's "explainability" story. We need a fixed, inspectable prompt; a machine-parseable
citation convention that maps an answer back to `chunks → documents → sources`; and a defined
behavior when retrieval finds nothing.

## Decision

**Message structure** sent through `LLMClient` (provider-agnostic — identical on Gemini and
Ollama):

- `system`: a fixed instruction, versioned in code as `PROMPT_VERSION = "rag-v1"`. It tells
  the assistant to answer **only** from the provided context; to cite with bracketed numerals
  `[n]` that refer to the numbered context items; to say plainly when the context doesn't
  contain the answer; and to never invent citations or facts not in context.
- **prior conversation turns** (user/assistant), oldest→newest, capped to the last
  `history_window = 6` messages so follow-ups work without unbounded prompt growth.
- `user`: the **context block** followed by the question.

**Context block format** — one numbered entry per retrieved chunk, in fused-rank order:

```
[1] (source: {source.name} · doc: {document.title})
{chunk.content}

[2] (source: {source.name} · doc: {document.title})
{chunk.content}
```

**Citation contract:** the model writes inline markers like `[1]`, `[2]`. After generation we
parse `\[(\d+)\]` markers, map each to its context entry → `chunk_id / document_id /
source_id`, and return them in `citations[]` (deduped, in first-appearance order). **All**
`top_k` retrieved chunks are persisted to `retrievals` (the full evidence set); `citations[]`
is the subset the model actually referenced. Out-of-range markers are ignored.

**Grounding / refusal:** if retrieval returns **zero** chunks, **short-circuit — do not call
the LLM** (saves free-tier quota and removes all hallucination risk). Persist the user message
and an assistant message with a fixed body ("I don't have anything in your notes about that
yet."), `model = null`, and no `retrievals`.

## Consequences

- **Good:** deterministic, provider-agnostic citations; explainable answers; the zero-context
  path can't hallucinate and costs no API call.
- **Good:** `PROMPT_VERSION` is the exact seam Phase 3 formalizes into MLflow prompt
  versioning + A/B + rollback.
- **Cost / limits:** a weak model can occasionally mis-emit `[n]`; we clamp/ignore rather than
  hard-fail. The prompt version is **not** persisted per message in Phase 1 (no column for it)
  — it lives in code until Phase 3 adds storage. The history budget is a message count, not a
  token-accurate window — fine for the MVP.
- **Privacy:** on the default Gemini path the system prompt + context + question transit to
  Google (ADR-0001). `options.private_mode` / Ollama keeps the whole turn local.

## Alternatives considered

- **Structured / JSON tool-output citations:** more robust parsing, but couples to
  provider-specific tool-use semantics and complicates the Ollama path. Deferred.
- **Always calling the LLM, even with no context:** wastes quota and invites hallucination.
  Rejected in favor of the short-circuit.
- **Unbounded history:** simpler, but grows prompt + cost without bound. Rejected for a fixed
  window.
