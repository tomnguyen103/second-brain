# ADR-0009 — Prompt versioning, A/B, and rollback

- **Status:** Accepted
- **Date:** 2026-06-02
- **Deciders:** project owner (accepted at recommended defaults under the `/goal` directive)
- **Context phase:** Phase 3 (Evaluation + MLOps)

## Context

The JD asks for A/B testing and rollback strategies. The lowest-risk, highest-leverage thing to
version in a RAG app is the **prompt** (the model and retrieval are already swappable by config —
ADR-0001/0005). Phase 1 hard-coded a single `SYSTEM_PROMPT` constant (`PROMPT_VERSION = "rag-v1"`
was a label only). We need named prompt versions, a way to select the active one per request, a
way to A/B two versions under the eval harness (ADR-0008), and an instant rollback path — without
breaking the 37 existing Phase 1/2 tests that import `SYSTEM_PROMPT`/`build_messages`.

## Decision

**In-code prompt registry (`app/chat/prompt.py`).** A frozen `PromptSpec{version, system_prompt,
refusal_text}` and `PROMPTS: dict[str, PromptSpec]` keyed by version. `rag-v1` is the Phase 1
prompt **byte-for-byte**; `rag-v2` is a tighter variant with the same contract (context-only,
`[n]` citations, refuse-when-absent). `get_prompt(version)` resolves and fails loud on unknown.

**Selection by config.** `build_messages(..., prompt_version=...)` (default `rag-v1`) chooses the
system prompt; `chat.service` passes `settings.prompt_version` and uses the active version's
`refusal_text` on the zero-context path. The module constants `SYSTEM_PROMPT`/`REFUSAL_TEXT`/
`PROMPT_VERSION` remain as `rag-v1` aliases for backward compatibility.

**A/B.** The eval runner (ADR-0008) runs two configs that differ by `prompt_version` (and/or
`top_k`/`llm_provider`) and logs each as an MLflow run; the comparison is the MLflow UI / printed
table. The meaningful prompt A/B is `gemini` (rag-v1) vs `gemini-v2` (rag-v2) — a real LLM is
needed for the prompt to actually change the answer. MLflow's `prompt_version` param is the audit
trail tying metrics to the prompt that produced them.

**Rollback.** The active prompt is `SECOND_BRAIN_PROMPT_VERSION`. Rolling back a regressed prompt
is **setting the env var back** (e.g. `rag-v2 → rag-v1`) and restarting — no code change, no
deploy, instant. New versions are added to the registry in code (diff-reviewable) and only become
active when selected.

## Consequences

- **Good:** prompt changes are versioned, reviewable (a code diff), A/B-able, and roll back in one
  env var. The eval harness quantifies a new prompt *before* it's made active.
- **Good:** zero breakage — `rag-v1` is unchanged and the old constants still resolve, so all 37
  prior tests pass; the new behaviour is purely additive.
- **Cost:** the registry lives in code, so adding a version is a deploy (not a runtime DB edit).
  Acceptable — prompts are code-like and benefit from review; a runtime registry (DB) is more
  moving parts than a one-user app needs.
- **Constraint:** a deterministic (`fake`) A/B can't show prompt-quality differences (the canned
  answer ignores the prompt); the real comparison requires the Gemini run.

## Alternatives considered

- **DB / MLflow Prompt Registry.** Runtime-editable prompts without a deploy, but more
  infrastructure and a mutable-prod-prompt risk. The in-code registry + env-var selection is
  simpler and safer for one user; revisit if non-engineers need to edit prompts.
- **Versioning the whole config (model + retrieval + prompt) as one artifact.** Cleaner lineage,
  but heavier; `EvalConfig` (ADR-0008) already bundles these for A/B, and prompt is the piece that
  changes most, so versioning it explicitly is the high-value 80/20.
- **Feature-flag service for rollout.** Overkill for a single-user app; an env var is the
  equivalent rollback lever here.
