# Second Brain — Phase 0 Data Model (ER Diagram)

> **Status:** implemented. The original Phase 0 schema has since grown through Alembic migrations;
> this document captures the relational spine plus the major supporting tables.

This is the relational spine for the whole project: the `sources → documents → chunks → embeddings`
ingest lineage, the `conversations → messages → retrievals → feedback` chat/evidence lineage, plus
governance (`audit_log`) and pipeline (`jobs`) tables that the plan calls for.

---

## ER diagram

```mermaid
erDiagram
    sources ||--o{ documents : "has"
    documents ||--o{ chunks : "split into"
    chunks ||--o{ embeddings : "embedded as"
    documents }o--o{ tags : "via document_tags"
    documents ||--o{ document_tags : ""
    tags ||--o{ document_tags : ""
    conversations ||--o{ messages : "contains"
    messages ||--o{ retrievals : "cited by"
    chunks ||--o{ retrievals : "evidence in"
    messages ||--o{ feedback : "rated by"

    sources {
        bigint      id PK
        text        type          "enum: notes_folder|github|rss|pdf_upload|bookmark|research_note|manual"
        text        name
        text        uri           "nullable — path/url of origin"
        jsonb       config         "source-specific settings"
        timestamptz created_at
        timestamptz updated_at
    }

    documents {
        bigint      id PK
        bigint      source_id FK
        text        title
        text        external_id    "nullable — original id/url at source"
        text        content_type   "mime: text/markdown, application/pdf, ..."
        char64      content_hash   "sha-256 of normalized raw text (dedupe)"
        text        raw_text       "nullable — PURGED after embedding (retention TTL)"
        jsonb       metadata       "flexible per-source fields; GIN-indexed"
        text        status         "enum: pending|chunked|embedded|failed"
        timestamptz ingested_at    "nullable"
        timestamptz created_at
        timestamptz updated_at
    }

    chunks {
        bigint      id PK
        bigint      document_id FK
        int         chunk_index    "ordinal within document"
        text        content        "the retrievable unit text"
        int         token_count
        int         char_start     "offset into source doc"
        int         char_end
        tsvector    tsv            "GENERATED from content; GIN index"
        jsonb       metadata
        timestamptz created_at
    }

    embeddings {
        bigint      id PK
        bigint      chunk_id FK
        text        model          "e.g. sentence-transformers/all-MiniLM-L6-v2"
        smallint    dim            "e.g. 384"
        vector      embedding      "vector(384); HNSW index"
        timestamptz created_at
    }

    tags {
        bigint      id PK
        text        name           "unique"
        timestamptz created_at
    }

    document_tags {
        bigint      document_id PK,FK
        bigint      tag_id PK,FK
    }

    conversations {
        bigint      id PK
        text        title          "nullable; auto-titled from first msg"
        timestamptz created_at
        timestamptz updated_at
    }

    messages {
        bigint      id PK
        bigint      conversation_id FK
        text        role           "enum: user|assistant|system"
        text        content
        text        model          "nullable — which LLM produced an assistant msg"
        jsonb       token_usage    "nullable — {prompt, completion, total}"
        int         latency_ms     "nullable — generation latency (eval metric)"
        timestamptz created_at
    }

    retrievals {
        bigint      id PK
        bigint      message_id FK   "the assistant answer that used this evidence"
        bigint      chunk_id FK
        int         rank
        double      score           "fused score"
        double      vector_score    "nullable"
        double      fulltext_score  "nullable"
        text        method          "enum: vector|fulltext|hybrid"
        timestamptz created_at
    }

    feedback {
        bigint      id PK
        bigint      message_id FK   "assistant message being rated"
        smallint    rating          "-1 down | +1 up"
        text        comment         "nullable"
        timestamptz created_at
    }
```

### Supporting tables (governance + pipeline — modeled now, used later)

```mermaid
erDiagram
    audit_log {
        bigint      id PK
        text        actor
        text        action          "read|create|update|delete|export"
        text        entity_type
        bigint      entity_id
        jsonb       detail
        timestamptz created_at
    }

    jobs {
        bigint      id PK
        text        type            "enum: ingest|embed|briefing|research"
        jsonb       payload
        text        status          "enum: queued|running|done|failed"
        int         attempts
        text        last_error      "nullable"
        timestamptz scheduled_at
        timestamptz started_at      "nullable"
        timestamptz finished_at     "nullable"
        timestamptz created_at
    }

    eval_cases {
        bigint      id PK
        text        case_id         "unique; reviewed eval case label"
        bigint      feedback_id FK  "nullable if source feedback is erased"
        text        question
        jsonb       expected_docs
        jsonb       expected_keywords
        boolean     expect_refusal
        jsonb       review          "review provenance + confirmations"
        timestamptz created_at
    }
```

---

## Indexes (planned)

| Table | Index | Purpose |
|---|---|---|
| `documents` | `UNIQUE (source_id, content_hash)` | dedupe — never ingest the same item twice per source |
| `documents` | `GIN (metadata jsonb_path_ops)` | queryable flexible metadata |
| `documents` | `btree (source_id)`, `btree (status)` | lineage + pipeline scans |
| `chunks` | `UNIQUE (document_id, chunk_index)` | stable chunk ordering |
| `chunks` | `GIN (tsv)` | full-text / lexical retrieval |
| `embeddings` | `HNSW (embedding vector_cosine_ops)` | approximate nearest-neighbour vector search |
| `embeddings` | `UNIQUE (chunk_id, model)` | one vector per chunk per model |
| `messages` | `btree (conversation_id, created_at)` | thread reads |
| `retrievals` | `btree (message_id)`, `btree (chunk_id)` | citation lookups both directions |
| `feedback` | `btree (message_id)` | answer-quality analytics |
| `jobs` | `btree (status, scheduled_at)` | worker poll |
| `eval_cases` | `UNIQUE (case_id)`, `btree (feedback_id)` | durable reviewed eval-case storage |

---

## Open design decisions (need your sign-off)

These are the "real decisions" AGENTS.md says get an ADR. I have a recommendation for each; the
schema above assumes the **recommended** option. Confirm or override and I'll lock them into ADRs.

### D1 — Embeddings: separate table, single fixed model/dim (→ **ADR-0002**)
A pgvector column has a **fixed dimension**, so multi-model support isn't free. I kept `embeddings`
as a *separate* table (not a column on `chunks`) with `vector(384)` for
`all-MiniLM-L6-v2`. **Recommendation:** one active model, dim 384, but keep the table separable so a
future re-embed with a different model is an additive migration, not a rewrite. *Alternative:* collapse
into `chunks.embedding` (simpler, but couples re-embedding to the chunk row).

### D2 — Chunking strategy (→ **ADR-0003**)
Schema stores `token_count`, `char_start/end`, `chunk_index` — strategy-agnostic. But the *values* need
a policy. **Recommendation:** ~512-token chunks, ~15% overlap, split on semantic boundaries
(headings/paragraphs) with a token-count fallback. This is the classic safe default for MiniLM-class
models. Want me to write the ADR proposing this, or do you have a target chunk size in mind?

### D3 — Pipeline trigger: `jobs` table vs `LISTEN/NOTIFY` (→ **ADR-0004**)
The plan flags this explicitly. **Recommendation:** include a `jobs` table now (durable, restart-safe,
inspectable — survives a worker crash) and use `LISTEN/NOTIFY` only as a low-latency *wake-up* signal on
top of it. Pure NOTIFY loses events if no listener is connected. *Alternative:* NOTIFY-only (less infra,
but at-most-once delivery).

### D4 — Keys: `bigint` identity vs `uuid`
Diagram uses `bigint GENERATED ALWAYS AS IDENTITY` (smaller, faster joins/indexes, fine for single-user).
**Recommendation:** keep bigint. Switch to uuid only if you ever want client-generated IDs or to hide row
counts. Single-user app → bigint wins.

### D5 — `raw_text` retention
`documents.raw_text` is nullable on purpose: store on ingest, then null it out after the retention TTL
while preserving chunks for retrieval. This reduces duplicate raw-source storage but is not
anonymization; source erasure is the path that removes documents, chunks, and embeddings.

---

## What's intentionally NOT here yet
- **RLS policies / `audit_log` triggers** — Phase 6 hardening. Tables are modeled; policies come later.
- **Materialized views** (latency percentiles, most-cited sources) — Phase 3/6 analytics, built on this spine.
- **`research_note` flow** — reuses `sources`(type=research_note) → `documents`; no new tables needed.
