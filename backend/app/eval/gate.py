"""CI eval gate (Phase 6, ADR-0012 / ADR-0008).

The quality gate the deploy pipeline runs: execute the eval set on the deterministic `baseline`
config (fake LLM — reproducible and keyless in CI) and fail the build if retrieval/citation
quality regresses below threshold. Thresholds cover LLM-independent metrics only
(`hit_at_k`, `citation_validity`, `refusal_accuracy`); answer-text quality (keyword recall,
latency) needs the real `gemini` run and is checked manually, not in CI (ADR-0008 D2/D3).
"""
from __future__ import annotations

import sys

# Deterministic floor for the fake-driver baseline. Phase 3 measured hit@k = citation = 1.000,
# refusal_accuracy = 0.923 — these thresholds sit safely below with margin for dataset growth.
DEFAULT_THRESHOLDS: dict[str, float] = {
    "hit_at_k": 0.80,
    "citation_validity": 0.90,
    "refusal_accuracy": 0.90,
}


def check_thresholds(
    aggregate: dict, thresholds: dict[str, float]
) -> tuple[bool, list[str]]:
    """Return (ok, failures). A metric fails if it is missing or below its threshold."""
    failures: list[str] = []
    for metric, minimum in thresholds.items():
        value = aggregate.get(metric)
        if value is None:
            failures.append(f"{metric}: missing (expected >= {minimum})")
        elif value < minimum:
            failures.append(f"{metric}: {value:.3f} < {minimum}")
    return (not failures, failures)


def main(argv: list[str] | None = None) -> int:
    """Run the baseline eval and return 0 if all thresholds pass, 1 otherwise (CI gate)."""
    # Heavy imports deferred so import/--help stays fast and model-free.
    from app.db.session import SessionLocal
    from app.embeddings.encoder import Embedder
    from app.eval.configs import CONFIGS
    from app.eval.dataset import load_corpus, load_dataset
    from app.eval.harness import run_eval
    from app.ingest.service import DocumentInput, SourceSpec, ingest_documents

    embedder = Embedder()
    dataset = load_dataset()
    db = SessionLocal()
    try:
        docs = [DocumentInput(title=d.title, content=d.content) for d in load_corpus()]
        res = ingest_documents(
            db, embedder, source=SourceSpec(type="manual", name="Eval Corpus"), documents=docs
        )
        report = run_eval(
            db, embedder, dataset, CONFIGS["baseline"], source_ids=[res.source_id]
        )
    finally:
        db.close()

    ok, failures = check_thresholds(report.aggregate, DEFAULT_THRESHOLDS)
    print("eval gate - baseline config (fake LLM)")
    for metric in sorted(DEFAULT_THRESHOLDS):
        value = report.aggregate.get(metric)
        shown = "n/a" if value is None else f"{value:.3f}"
        print(f"  {metric:<20} {shown:>8}  (min {DEFAULT_THRESHOLDS[metric]})")
    if ok:
        print("PASSED")
        return 0
    print("FAILED:", file=sys.stderr)
    for f in failures:
        print(f"  - {f}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
