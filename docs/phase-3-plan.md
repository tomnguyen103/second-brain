# Phase 3 — Evaluation + MLOps Implementation Plan

> **For agentic workers:** work TDD (red → green → commit), DRY, YAGNI. Steps use checkbox
> (`- [ ]`) syntax. Pure logic is DB-free and unit-tested; the harness end-to-end is integration-
> tested against a real Postgres. Commit after each green task.

**Goal:** Make answer quality *measurable and improvable*. Ship (1) a curated **eval set**
(questions + expected sources/keywords + a deliberate refusal case), (2) a **metrics** module
(retrieval recall@k / hit@k / MRR, citation validity, keyword recall, refusal correctness,
latency p50/p95), (3) an **eval harness** that runs the real RAG pipeline over the set for a
named config and (4) logs params + metrics + a per-case artifact to **MLflow**, (5) an **A/B**
runner that compares two configs, and (6) **prompt versioning with rollback** behind config.

**Architecture:** all $0 / self-hosted. MLflow writes to a **local file store** (`./mlruns`) —
no server, no recurring bill; `mlflow ui` reads it for the shareable comparison screenshot.
The harness reuses the Phase 1 seams: `hybrid_search` (read-only retrieval), `build_messages`
(now prompt-versioned), and the `LLMClient` (`fake` for deterministic CI, `gemini` for the real
run). Retrieval metrics need no LLM; answer metrics use whatever driver the config selects.

**Tech stack delta:** `mlflow>=2.14,<3` (local tracking; validated install = 2.22.5), `pyyaml`
(dataset). Python 3.12 venv (via `uv`). Postgres 16 + pgvector via the existing compose DB (5433).

---

## Decisions (recommended defaults — accepted under the `/goal` directive, revisable)

- **D1 — MLflow tracking = local file store (`file:./mlruns`).** $0, no server, no daemon; the
  comparison is viewable via `mlflow ui`. *Gave up:* a shared/remote tracking server (revisit in
  Phase 6 if the VPS hosts MLflow). Backend overridable via `SECOND_BRAIN_MLFLOW_TRACKING_URI`.
- **D2 — Deterministic eval by default (`fake` LLM), real run is opt-in (`gemini`).** CI and the
  harness integration test must be reproducible and network-free, so the default A/B uses the
  `fake` driver; the shareable MLflow comparison is generated with a documented `--config gemini`
  run. Retrieval metrics are identical across drivers (LLM-independent). *Gave up:* answer-quality
  realism in CI — covered by the manual `gemini` run.
- **D3 — Answer-quality metrics are deterministic (no LLM-as-judge in v1).** Citation validity
  (markers in range), keyword recall (expected substrings present), and refusal correctness are
  computable without a second model — cheap, stable, no extra cost. *Gave up:* nuanced semantic
  grading; LLM-as-judge is a documented Phase 3.5/6 extension behind the same `LLMClient`.
- **D4 — Eval corpus is a small fixed set committed in-repo (`backend/eval/corpus/*.md`).** ~6
  short notes on distinct topics so retrieval has signal; ~12 questions incl. multi-source and one
  refusal. Re-ingested idempotently (content-hash dedupe) into the dev DB by the runner. *Gave up:*
  a large realistic corpus — fine for a methodology demo; grow later.
- **D5 — Prompt versioning = an in-code registry keyed by version string.** `PROMPTS["rag-v1"]`
  (the current prompt, unchanged) and `PROMPTS["rag-v2"]` (a variant). `build_messages` takes
  `prompt_version`; `settings.prompt_version` selects the active one. **Rollback = set the env var
  back** (`SECOND_BRAIN_PROMPT_VERSION=rag-v1`) — instant, no deploy. A/B = the runner runs two
  configs differing by `prompt_version` (and/or `top_k`/`llm_provider`). *Gave up:* a DB/MLflow
  prompt registry — the in-code registry is simpler and diff-reviewable; MLflow logs which version
  produced which metrics, which is the versioning audit trail the JD asks for.

---

## File structure (created/modified in this phase)

```
backend/
  requirements.txt                 # MODIFY: add mlflow, pyyaml
  app/
    config.py                      # MODIFY: prompt_version + mlflow_* settings
    chat/prompt.py                 # MODIFY: prompt registry + versioned build_messages (compat)
    chat/service.py                # MODIFY: pass settings.prompt_version into build_messages
    eval/
      __init__.py                  # CREATE
      dataset.py                   # CREATE: EvalCase + load_dataset(yaml)
      metrics.py                   # CREATE: recall@k/hit@k/mrr/citation/keyword/refusal/aggregate
      configs.py                   # CREATE: EvalConfig + named configs (baseline/variant/gemini)
      pipeline.py                  # CREATE: answer_question() — read-only retrieve+generate (no persist)
      harness.py                   # CREATE: run_eval(...) -> EvalReport
      mlflow_logger.py             # CREATE: log_report(report, uri, experiment)
      runner.py                    # CREATE: __main__ CLI — ingest corpus, run configs, log, print table
  eval/
    corpus/*.md                    # CREATE: ~6 fixed eval documents
    dataset.yaml                   # CREATE: questions + expected sources/keywords/refusal
  tests/
    unit/test_prompt_versions.py   # CREATE (DB-free)
    unit/test_eval_dataset.py      # CREATE (DB-free)
    unit/test_eval_metrics.py      # CREATE (DB-free)
    unit/test_eval_mlflow.py       # CREATE (DB-free; tmp file store)
    integration/test_eval_harness.py  # CREATE (DB-bound; ingest corpus, run with fake llm)
  README.md                        # MODIFY: Phase 3 run/verify (eval + mlflow ui)
docs/
  adr/0008-evaluation-and-mlflow.md      # CREATE
  adr/0009-prompt-versioning-ab-rollback.md  # CREATE
  adr/README.md                          # MODIFY: index 0008/0009
  PROGRESS.md                            # MODIFY: Phase 3 → in progress → complete
  implementation-notes.md                # MODIFY: any off-spec calls
```

---

## Task 1 — Deps + config (DB-free)
**Files:** `requirements.txt`, `app/config.py`; test `tests/unit/test_config.py`.
- [ ] Add `mlflow>=2.14,<3` and `pyyaml>=6,<7` to requirements (Phase 3 block).
- [ ] Add to `Settings`: `prompt_version: str = "rag-v1"`, `mlflow_tracking_uri: str = "file:./mlruns"`,
      `mlflow_experiment: str = "second-brain-rag"`.
- [ ] Extend `test_defaults` (hermetic, `_env_file=None`) to assert `prompt_version == "rag-v1"`.
- [ ] Run unit tests → PASS. Commit `feat(config): phase-3 prompt-version + mlflow settings`.

## Task 2 — Prompt versioning registry (DB-free)
**Files:** `app/chat/prompt.py`, `app/chat/service.py`; test `tests/unit/test_prompt_versions.py`.
- [ ] Introduce `@dataclass PromptSpec{version, system_prompt, refusal_text}` and
      `PROMPTS: dict[str, PromptSpec]` with `rag-v1` (= current `SYSTEM_PROMPT`/`REFUSAL_TEXT`,
      byte-for-byte) and a `rag-v2` variant (tighter wording; still "answer only from context, cite
      with [n], refuse when absent"). Keep module constants `SYSTEM_PROMPT`/`REFUSAL_TEXT`/
      `PROMPT_VERSION` as `rag-v1` aliases for backward compatibility.
- [ ] `get_prompt(version) -> PromptSpec` (raises on unknown). `build_messages(..., prompt_version="rag-v1")`
      uses `get_prompt(version).system_prompt`. **Existing callers/tests keep passing** (default arg).
- [ ] `chat/service.py`: pass `prompt_version=settings.prompt_version` into `build_messages`, and use
      `get_prompt(settings.prompt_version).refusal_text` for the zero-context branch.
- [ ] Tests: both versions resolve; unknown raises; `build_messages` swaps the system prompt; refusal
      text follows the version. Run full unit suite → PASS. Commit `feat(chat): prompt-version registry (ADR-0009)`.

## Task 3 — Eval dataset + corpus (DB-free loader)
**Files:** `app/eval/dataset.py`, `eval/dataset.yaml`, `eval/corpus/*.md`; test `tests/unit/test_eval_dataset.py`.
- [ ] `@dataclass EvalCase{id, question, expected_sources: list[str], expected_keywords: list[str],
      expect_refusal: bool=False}`; `load_dataset(path) -> list[EvalCase]` (PyYAML; validates required keys,
      unique ids).
- [ ] Author ~6 corpus markdown notes (distinct topics: e.g. hnsw-tuning, rrf-fusion, postgres-fts,
      docker-compose, fastapi-app, embeddings-minilm) and `dataset.yaml` (~12 cases incl. ≥1 multi-source
      and exactly one `expect_refusal: true` about an off-corpus topic).
- [ ] Test loads the committed dataset: count, unique ids, the refusal case parses, every
      `expected_sources` entry names a real corpus doc. Run → PASS. Commit `feat(eval): dataset schema + corpus + loader`.

## Task 4 — Metrics (DB-free, pure)
**Files:** `app/eval/metrics.py`; test `tests/unit/test_eval_metrics.py`.
- [ ] Pure functions over `retrieved_sources: list[str]` (rank order) + `expected_sources: list[str]`:
      `hit_at_k`, `recall_at_k`, `mrr`; over answer text: `citation_validity(answer, n_context) -> float`,
      `keyword_recall(answer, keywords) -> float`, `refusal_correct(answer, expect_refusal, refusal_text) -> bool`.
      `aggregate(rows) -> dict` (means + `latency_p50_ms`/`latency_p95_ms` + counts).
- [ ] Unit tests with hand-built rows: perfect hit, miss, partial recall, MRR at rank 2, out-of-range
      citation, keyword present/absent, correct/incorrect refusal, aggregate math + percentiles.
      Run → PASS. Commit `feat(eval): retrieval + answer-quality metrics`.

## Task 5 — Read-only answer pipeline + configs (DB-free configs; pipeline DB-bound)
**Files:** `app/eval/pipeline.py`, `app/eval/configs.py`; configs unit-tested.
- [ ] `answer_question(db, embedder, llm, settings, question, *, top_k) -> AnswerResult{answer,
      retrieved_sources, n_context, latency_ms, cited_markers}` — reuses `hybrid_search` +
      `load_display_chunks` + `build_messages(prompt_version=settings.prompt_version)` + `llm.generate`,
      **without persisting** conversations/messages (eval must not pollute history). Zero-context →
      refusal text, no LLM call (mirrors `chat.service`).
- [ ] `@dataclass EvalConfig{name, llm_provider, prompt_version, top_k}`; `CONFIGS` with
      `baseline`(rag-v1,fake,k=5), `variant`(rag-v2,fake,k=8), `gemini`(rag-v1,gemini,k=5).
      `settings_for(config)` clones Settings with overrides. Unit-test the registry + override mapping.
- [ ] Commit `feat(eval): read-only answer pipeline + A/B configs`.

## Task 6 — Harness (DB-bound)
**Files:** `app/eval/harness.py`; test `tests/integration/test_eval_harness.py`.
- [ ] `run_eval(db, embedder, dataset, config, *, llm=None) -> EvalReport` — per case: `answer_question`,
      map hits→source names, compute per-case metrics (`metrics.py`), collect latency; `aggregate(...)`.
      `EvalReport{config, rows, aggregate}`. LLM defaults to `get_llm_client(settings_for(config))`,
      injectable for tests (`fake`).
- [ ] Integration test (skips w/o `SECOND_BRAIN_TEST_DATABASE_URL`): ingest the corpus with the
      `fake_embedder`, run `run_eval` with the `baseline` config + `FakeLLMClient`; assert report has a
      row per case, `hit_at_k`∈[0,1], refusal case scores `refusal_correct=True`, aggregate keys present.
      Run (DB up) → PASS. Commit `feat(eval): pipeline harness over the eval set`.

## Task 7 — MLflow logger (DB-free)
**Files:** `app/eval/mlflow_logger.py`; test `tests/unit/test_eval_mlflow.py`.
- [ ] `log_report(report, *, tracking_uri, experiment) -> run_id` — set tracking URI + experiment,
      start a run named `config.name`, `log_params` (llm_provider, prompt_version, top_k, dataset_size),
      `log_metrics` (aggregate), `log_dict` the per-case rows as `eval_results.json` artifact.
- [ ] Test against a **tmp file store** (`file:<tmpdir>/mlruns`): log a synthetic report, then read back
      via `mlflow.tracking.MlflowClient` — assert the run exists with the expected params/metrics. Run →
      PASS. Commit `feat(eval): MLflow logging (params, metrics, per-case artifact)`.

## Task 8 — Runner CLI / A-B entrypoint (DB-bound; manual)
**Files:** `app/eval/runner.py`.
- [ ] `python -m app.eval.runner --configs baseline,variant [--no-mlflow]` — connect DB, ingest corpus
      (idempotent), load dataset, real `Embedder`; for each config run `run_eval` → `log_report` → collect
      aggregate; print a side-by-side comparison table (metric × config) to stdout. Exit non-zero on error.
- [ ] Manual verify: `--configs baseline,variant` produces 2 MLflow runs + a printed table;
      `mlflow ui --backend-store-uri ./mlruns` shows the A/B comparison (shareable artifact).
- [ ] Commit `feat(eval): runner CLI + A/B comparison`.

## Task 9 — ADRs + docs (DB-free)
**Files:** `docs/adr/0008-*.md`, `docs/adr/0009-*.md`, `docs/adr/README.md`, `backend/README.md`,
`docs/PROGRESS.md`, `docs/implementation-notes.md`.
- [ ] ADR-0008 (eval methodology: dataset, metrics, deterministic-by-default, MLflow local store).
- [ ] ADR-0009 (prompt versioning + A/B + rollback mechanism).
- [ ] README "Phase 3 — run & verify" (run eval, open `mlflow ui`, rollback a prompt). Flip PROGRESS
      Phase 3 → ✅ with a dated log entry. Record any off-spec calls in implementation-notes.
- [ ] Commit `docs: phase-3 eval/MLOps ADRs + run/verify + progress`.

---

## Self-review (against spec + JD)
- Eval set (questions + expected sources) → Tasks 3 ✅
- Eval harness logging quality/latency/refusal to MLflow → Tasks 4,6,7 ✅
- A/B two configs → Tasks 5,8 ✅
- Prompt versioning + rollback → Tasks 2,8,9 (ADR-0009) ✅
- Tests alongside code (unit + integration vs real Postgres) → every task ✅
- $0 / no recurring bill (local MLflow store, free Gemini tier, fake driver for CI) → D1/D2 ✅
- Ends runnable + shareable (MLflow A/B comparison) → Task 8 ✅

## Known sharp edges (flagged, not placeholders)
1. **Eval must not pollute conversation history** → `answer_question` is read-only (no Message rows);
   do NOT call `chat.service.chat` in the harness.
2. **MLflow file-store URI on Windows** — use a forward-slash `file:./mlruns` relative URI; the test
   uses a tmp dir. Verify `mlflow ui --backend-store-uri ./mlruns` resolves on this box.
3. **Determinism** — the `fake` embedder must rank the expected source first for the keyword in each
   non-refusal case, or retrieval metrics in the integration test will be noisy. Keep the integration
   assertions tolerant (`hit_at_k ∈ {0,1}`, refusal-case exactness) and leave precise quality numbers to
   the real `gemini` run.
4. **Backward compatibility** — `build_messages`/`SYSTEM_PROMPT` keep their Phase 1/2 signatures and
   values (rag-v1) so all 37 existing tests stay green.
