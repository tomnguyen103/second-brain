# ADR-0003 — Chunking: ~512 tokens, ~15% overlap, semantic-boundary split

- **Status:** Accepted
- **Date:** 2026-06-01
- **Deciders:** project owner
- **Context phase:** Phase 0 (schema), applied in Phase 1 (ingest worker)

## Context

Retrieval quality depends heavily on chunk size: too large dilutes relevance and wastes the LLM context
budget; too small fragments meaning and inflates row counts. The default embedding model
(`all-MiniLM-L6-v2`) has a **256-word-piece effective window** but performs well on passage-sized inputs;
512 tokens is the widely used safe ceiling for this model class.

The Phase 0 schema is deliberately **strategy-agnostic** — `chunks` stores `chunk_index`, `token_count`,
`char_start`, `char_end`. This ADR fixes the *policy* the ingest worker applies, not the schema.

## Decision

- **Target size:** ~512 tokens per chunk.
- **Overlap:** ~15% (~75 tokens) between adjacent chunks, to preserve cross-boundary context.
- **Boundaries:** split on **semantic boundaries first** (headings, then paragraphs, then sentences),
  falling back to a hard token cut only when a single unit exceeds the target.
- **Provenance:** every chunk records `char_start`/`char_end` into the source document so citations can
  point at the exact span.

## Consequences

- **Good:** balanced relevance vs context cost; overlap reduces "answer split across two chunks" misses;
  char offsets give precise, verifiable citations.
- **Cost:** overlap duplicates ~15% of text across chunks (more rows, slightly more storage/embeddings).
  Acceptable for a personal corpus.
- **Revisit trigger:** if Phase 3 eval shows low retrieval hit-rate, sweep size/overlap as an A/B and
  record results — this ADR is the baseline to beat, not a permanent freeze.

## Alternatives considered

- **Fixed 256-token, no overlap:** cheaper, but more boundary-split misses. Rejected as default.
- **Whole-document embedding:** no chunking — poor for long docs, blows context budget. Rejected.
- **Recursive/semantic-only with no token cap:** unbounded chunk sizes break the embedding window.
  Rejected; we keep the token ceiling as a hard fallback.
