"""MLflow logging of an EvalReport (ADR-0008). DB-free; uses a tmp file store."""
from mlflow.tracking import MlflowClient

from app.eval.configs import EvalConfig
from app.eval.harness import EvalReport
from app.eval.mlflow_logger import log_report


def _report():
    return EvalReport(
        config=EvalConfig("baseline", "fake", "rag-v1", 5),
        rows=[
            {"id": "a", "hit": 1.0, "recall": 1.0, "mrr": 1.0, "citation_validity": 1.0,
             "keyword_recall": 1.0, "refusal_correct": True, "is_refusal": False,
             "latency_ms": 12.0, "answer": "ans [1]", "retrieved_docs": ["A"], "model": "fake"},
            {"id": "b", "hit": None, "recall": None, "mrr": None, "citation_validity": 1.0,
             "keyword_recall": None, "refusal_correct": True, "is_refusal": True,
             "latency_ms": 4.0, "answer": "refused", "retrieved_docs": [], "model": "fake"},
        ],
        aggregate={"n_cases": 2, "n_refusal_cases": 1, "hit_at_k": 1.0,
                   "refusal_accuracy": 1.0, "latency_p50_ms": 8.0},
    )


def test_log_report_creates_run_with_params_and_metrics(tmp_path):
    uri = (tmp_path / "mlruns").as_uri()
    run_id = log_report(_report(), tracking_uri=uri, experiment="test-exp")

    client = MlflowClient(tracking_uri=uri)
    run = client.get_run(run_id)
    assert run.data.params["config"] == "baseline"
    assert run.data.params["prompt_version"] == "rag-v1"
    assert run.data.params["top_k"] == "5"
    assert run.data.metrics["hit_at_k"] == 1.0
    assert run.data.metrics["n_cases"] == 2.0
    assert run.data.metrics["refusal_accuracy"] == 1.0

    # per-case artifact was written
    artifacts = [a.path for a in client.list_artifacts(run_id)]
    assert "eval_results.json" in artifacts


def test_two_configs_log_as_separate_runs(tmp_path):
    uri = (tmp_path / "mlruns").as_uri()
    r1 = _report()
    r2 = EvalReport(config=EvalConfig("variant", "fake", "rag-v2", 8),
                    rows=r1.rows, aggregate=r1.aggregate)
    id1 = log_report(r1, tracking_uri=uri, experiment="ab")
    id2 = log_report(r2, tracking_uri=uri, experiment="ab")
    assert id1 != id2
    client = MlflowClient(tracking_uri=uri)
    assert client.get_run(id2).data.params["prompt_version"] == "rag-v2"
