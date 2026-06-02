"""CI eval-gate threshold check (Phase 6). Pure / DB-free."""
from app.eval.gate import DEFAULT_THRESHOLDS, check_thresholds


def test_pass_when_all_meet_thresholds():
    agg = {"hit_at_k": 1.0, "citation_validity": 1.0, "refusal_accuracy": 0.95}
    ok, failures = check_thresholds(agg, DEFAULT_THRESHOLDS)
    assert ok is True
    assert failures == []


def test_fail_when_metric_below_threshold():
    agg = {"hit_at_k": 0.5, "citation_validity": 1.0, "refusal_accuracy": 0.95}
    ok, failures = check_thresholds(agg, DEFAULT_THRESHOLDS)
    assert ok is False
    assert any("hit_at_k" in f for f in failures)


def test_fail_when_metric_missing():
    agg = {"citation_validity": 1.0, "refusal_accuracy": 0.95}  # no hit_at_k
    ok, failures = check_thresholds(agg, DEFAULT_THRESHOLDS)
    assert ok is False
    assert any("hit_at_k" in f and "missing" in f for f in failures)


def test_boundary_value_passes():
    # exactly at the threshold is acceptable (>=)
    ok, _ = check_thresholds({"x": 0.8}, {"x": 0.8})
    assert ok is True
