"""Eval metrics (ADR-0008). Pure / DB-free."""
import math

from app.eval import metrics as m


def test_hit_at_k():
    assert m.hit_at_k(["A", "B", "C"], ["B"], k=2) == 1.0
    assert m.hit_at_k(["A", "B", "C"], ["C"], k=2) == 0.0   # C is rank 3, outside top-2
    assert m.hit_at_k(["A"], ["Z"], k=5) == 0.0


def test_recall_at_k():
    assert m.recall_at_k(["A", "B", "C"], ["A", "C"], k=3) == 1.0
    assert m.recall_at_k(["A", "B", "C"], ["A", "Z"], k=3) == 0.5
    assert m.recall_at_k(["A"], [], k=3) == 0.0             # empty expected → 0


def test_mrr():
    assert m.mrr(["A", "B", "C"], ["A"]) == 1.0
    assert m.mrr(["A", "B", "C"], ["B"]) == 0.5             # first hit at rank 2
    assert m.mrr(["A", "B", "C"], ["Z"]) == 0.0


def test_citation_validity():
    assert m.citation_validity("uses [1] and [2]", n_context=3) == 1.0
    assert m.citation_validity("uses grouped markers [1, 2]", n_context=3) == 1.0
    assert m.citation_validity("uses [1] and [9]", n_context=3) == 0.5   # [9] out of range
    assert m.citation_validity("no markers here", n_context=3) == 1.0    # nothing hallucinated


def test_keyword_recall():
    assert m.keyword_recall("ef_search trades recall for latency", ["ef_search", "latency"]) == 1.0
    assert m.keyword_recall("only one term: ef_search", ["ef_search", "missing"]) == 0.5
    assert m.keyword_recall("anything", []) == 1.0
    # case-insensitive
    assert m.keyword_recall("The RRF constant is 60", ["rrf", "60"]) == 1.0


def test_refusal_detection_and_correctness():
    rts = ["I don't have anything in your notes about that yet.", "That isn't in your notes yet."]
    assert m.is_refusal("That isn't in your notes yet.", rts) is True
    assert m.is_refusal("HNSW uses ef_search [1].", rts) is False
    assert m.refusal_correct("That isn't in your notes yet.", expect_refusal=True, refusal_texts=rts) is True
    assert m.refusal_correct("HNSW uses ef_search [1].", expect_refusal=True, refusal_texts=rts) is False
    assert m.refusal_correct("HNSW uses ef_search [1].", expect_refusal=False, refusal_texts=rts) is True


def test_percentile():
    assert m.percentile([10], 50) == 10.0
    assert m.percentile([10, 20], 50) == 15.0
    assert m.percentile([10, 20, 30, 40], 50) == 25.0
    assert m.percentile([], 95) == 0.0


def test_aggregate():
    rows = [
        {"hit": 1.0, "recall": 1.0, "mrr": 1.0, "citation_validity": 1.0, "keyword_recall": 1.0,
         "refusal_correct": True, "latency_ms": 10.0, "expected_refusal": False, "is_refusal": False},
        {"hit": 0.0, "recall": 0.0, "mrr": 0.0, "citation_validity": 0.5, "keyword_recall": 0.0,
         "refusal_correct": True, "latency_ms": 30.0, "expected_refusal": False, "is_refusal": False},
        # refusal case: retrieval metrics N/A (None); model did NOT actually refuse (is_refusal False)
        {"hit": None, "recall": None, "mrr": None, "citation_validity": 1.0, "keyword_recall": 1.0,
         "refusal_correct": False, "latency_ms": 5.0, "expected_refusal": True, "is_refusal": False},
    ]
    agg = m.aggregate(rows)
    assert agg["n_cases"] == 3
    assert agg["n_refusal_cases"] == 1          # by ground-truth label (expected_refusal)
    assert agg["n_refused_by_model"] == 0       # none actually refused
    assert agg["hit_at_k"] == 0.5            # mean of [1,0], None skipped
    assert agg["recall_at_k"] == 0.5
    assert math.isclose(agg["refusal_accuracy"], 2 / 3)   # 2 of 3 correct
    assert agg["latency_p50_ms"] == 10.0     # median of [5,10,30]
    # all values numeric (MLflow-ready)
    assert all(isinstance(v, (int, float)) for v in agg.values())
