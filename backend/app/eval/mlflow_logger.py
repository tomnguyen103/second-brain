"""Log an EvalReport to MLflow (ADR-0008).

Local file store by default (no server, $0). One run per config; params capture the config,
metrics are the aggregate, and the per-case rows are attached as a JSON artifact. Kept separate
from the harness so evaluation can run without MLflow installed/configured.
"""
from __future__ import annotations

import mlflow

from app.eval.harness import EvalReport


def log_report(report: EvalReport, *, tracking_uri: str, experiment: str) -> str:
    """Log one config's report as an MLflow run; returns the run id."""
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment)

    cfg = report.config
    with mlflow.start_run(run_name=cfg.name) as run:
        mlflow.log_params({
            "config": cfg.name,
            "llm_provider": cfg.llm_provider,
            "prompt_version": cfg.prompt_version,
            "top_k": cfg.top_k,
            "dataset_size": report.aggregate.get("n_cases", len(report.rows)),
        })
        # aggregate is numeric-only by construction (metrics.aggregate drops None)
        mlflow.log_metrics({k: float(v) for k, v in report.aggregate.items()})
        # full per-case detail as a reviewable artifact
        mlflow.log_dict({"config": cfg.name, "rows": report.rows}, "eval_results.json")
        return run.info.run_id
