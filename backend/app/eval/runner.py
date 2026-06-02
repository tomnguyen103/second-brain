"""Eval runner / A-B entrypoint (ADR-0008).

Ingests the fixed corpus into the configured DB (idempotent — content-hash dedupe), runs the
eval set for each named config, logs each as an MLflow run, and prints a side-by-side table.

Usage:
    python -m app.eval.runner --configs baseline,variant       # deterministic A/B (fake LLM)
    python -m app.eval.runner --configs gemini                 # real run (needs a Gemini key)
    python -m app.eval.runner --configs baseline,variant --no-mlflow
"""
from __future__ import annotations

import argparse
import sys

from app.config import settings
from app.db.session import SessionLocal
from app.eval.configs import CONFIGS
from app.eval.dataset import load_corpus, load_dataset
from app.eval.harness import EvalReport, run_eval
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents

_SOURCE = SourceSpec(type="manual", name="Eval Corpus")
_METRIC_ROWS = ["hit_at_k", "recall_at_k", "mrr", "citation_validity", "keyword_recall",
                "refusal_accuracy", "latency_p50_ms", "latency_p95_ms"]


def _ingest_corpus(db, embedder) -> int:
    docs = [DocumentInput(title=d.title, content=d.content) for d in load_corpus()]
    result = ingest_documents(db, embedder, source=_SOURCE, documents=docs)
    return len(result.documents)


def _print_table(reports: list[EvalReport]) -> None:
    names = [r.config.name for r in reports]
    col = 16
    header = "metric".ljust(20) + "".join(n.ljust(col) for n in names)
    print(header)
    print("-" * len(header))
    for metric in _METRIC_ROWS:
        cells = "".join(
            ("—".ljust(col) if (v := r.aggregate.get(metric)) is None else f"{v:.3f}".ljust(col))
            for r in reports
        )
        print(metric.ljust(20) + cells)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the RAG eval set for one or more configs.")
    parser.add_argument("--configs", default="baseline,variant",
                        help="comma-separated config names (default: baseline,variant)")
    parser.add_argument("--no-mlflow", action="store_true", help="skip MLflow logging")
    args = parser.parse_args(argv)

    names = [n.strip() for n in args.configs.split(",") if n.strip()]
    unknown = [n for n in names if n not in CONFIGS]
    if unknown:
        print(f"unknown config(s): {unknown}; available: {sorted(CONFIGS)}", file=sys.stderr)
        return 2

    # Heavy import deferred so --help / arg errors stay fast and model-free.
    from app.embeddings.encoder import Embedder
    embedder = Embedder()
    dataset = load_dataset()
    reports: list[EvalReport] = []

    db = SessionLocal()
    try:
        n = _ingest_corpus(db, embedder)
        print(f"ingested/deduped {n} corpus docs; "
              f"running {len(dataset)} cases x {len(names)} config(s)\n")
        for name in names:
            report = run_eval(db, embedder, dataset, CONFIGS[name])
            reports.append(report)
            if not args.no_mlflow:
                from app.eval.mlflow_logger import log_report
                run_id = log_report(report, tracking_uri=settings.mlflow_tracking_uri,
                                    experiment=settings.mlflow_experiment)
                print(f"[{name}] logged MLflow run {run_id}")
    finally:
        db.close()

    print()
    _print_table(reports)
    if not args.no_mlflow:
        store = settings.mlflow_tracking_uri.replace("file:", "")
        print(f"\nopen the comparison:  mlflow ui --backend-store-uri {store}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
