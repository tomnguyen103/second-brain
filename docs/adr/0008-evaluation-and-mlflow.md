# ADR-0008 — Evaluation methodology + MLflow tracking

- **Status:** Accepted
- **Date:** 2026-06-02
- **Deciders:** project owner (accepted at recommended defaults under the `/goal` directive)
- **Context phase:** Phase 3 (Evaluation + MLOps)

> **Runtime update 2026-06-05:** ADR-0015 changes the cost guardrail to "no recurring
> infrastructure bill by default." The local MLflow file-store decision still stands.

## Context

Phase 3 makes answer quality *measurable and improvable* — the JD weights evaluation, A/B, and
MLOps heavily. We need: a repeatable eval set, metrics that capture retrieval quality, answer
quality, and latency, a harness that runs the **real** RAG pipeline over the set, and a place to
log/compare runs (MLflow is the locked tool, AGENTS.md). Constraints from AGENTS.md: **no
recurring bill beyond the one VPS**, and the pipeline must stay testable in CI with **no network
and no key** (the `fake` driver path established in ADR-0001/0007).

## Decision

**Eval set (`backend/eval/`).** A small fixed corpus of markdown notes (one topic per file; the
first H1 is the document title) plus a `dataset.yaml` of cases: `question`, `expected_docs`
(document titles retrieval should surface), `expected_keywords` (substrings a faithful answer
should contain), and `expect_refusal` for the one deliberate off-corpus case. Retrieval is scored
at **document granularity** (the natural unit for a one-topic-per-file corpus).

**Metrics (`app/eval/metrics.py`, pure/DB-free).**
- *Retrieval:* `hit@k`, `recall@k`, `MRR` over the rank-ordered distinct retrieved documents.
- *Answer:* `citation_validity` (fraction of emitted `[n]` markers that point at a real context
  item — catches hallucinated citations), `keyword_recall` (expected substrings present),
  `refusal_correct` (refused iff `expect_refusal`).
- *Latency:* p50 / p95 / mean.
- `aggregate()` rolls per-case rows into MLflow-ready numbers; retrieval metrics are N/A (None)
  for the refusal case and are skipped in the mean.

**Harness (`app/eval/harness.py`).** Reuses the Phase 1 seams through a **read-only** pipeline
(`app/eval/pipeline.py`): `hybrid_search` → `build_messages` → `LLMClient.generate`, persisting
**nothing** (eval must not pollute conversation history). One `EvalReport` per config.

**MLflow = local file store (`file:./mlruns`), no server.** `app/eval/mlflow_logger.py` logs one
run per config: params (config, llm_provider, prompt_version, top_k, dataset_size), metrics (the
aggregate), and the per-case rows as an `eval_results.json` artifact. `mlflow ui --backend-store-uri
./mlruns` renders the A/B comparison. `mlruns/` is gitignored.

**Deterministic by default.** The default A/B (`baseline`/`variant`) uses the `fake` driver so CI
and the harness integration test are reproducible and network-free; retrieval metrics are
LLM-independent. Answer-quality metrics (keyword recall, refusal-on-irrelevance, latency) are only
meaningful on the real-LLM run — the opt-in `gemini` / `gemini-v2` configs (need a Gemini key).

## Consequences

- **Good:** every JD eval bullet has a concrete home (metrics incl. latency + a
  grounding/refusal check, MLflow versioned runs, an A/B comparison). `$0` — local file store,
  free Gemini tier, `fake` driver for CI.
- **Good:** the harness exercises the *real* retrieval pipeline, so retrieval numbers are honest
  even with the `fake` LLM (full-text carries relevance). Verified live: `hit@k = recall@k = 1.0`,
  `MRR ≈ 0.92` over the 13-case set.
- **Limitation:** with the `fake` driver, `keyword_recall = 0` and `latency ≈ 0` by construction,
  and the refusal case isn't refused (the canned answer ignores context). These are expected; the
  `gemini` run produces the meaningful answer-quality numbers. Documented in the runner output and
  README.
- **Scope deferred:** LLM-as-judge grading (a second model scoring answers) — behind the same
  `LLMClient` seam — is a Phase 3.5/6 extension; v1 metrics are deterministic on purpose.

## Alternatives considered

- **MLflow tracking server / SQLite backend.** More features (UI always-on, multi-user), but a
  server is operational weight and (if hosted) a bill. The file store gives the same run/compare
  story for one user at `$0`; revisit if the VPS hosts MLflow in Phase 6.
- **LLM-as-judge in v1.** Richer semantic grading, but non-deterministic, adds cost, and would
  make CI flaky. Deferred in favour of deterministic metrics now.
- **Evaluating via `chat.service.chat` directly.** Reuses more code, but it persists conversations
  and messages — evaluation would pollute history and analytics. Rejected for the read-only
  `answer_question` pipeline.
- **Reranking / larger corpus.** Out of scope for the methodology demo; the harness scales to a
  bigger dataset.yaml without code changes.
