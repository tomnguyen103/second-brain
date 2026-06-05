"""Evaluation metrics (ADR-0008). Pure, DB-free.

Retrieval quality (over ranked document-title lists): hit@k, recall@k, MRR.
Answer quality (over answer text): citation validity, keyword recall, refusal correctness.
Plus latency percentiles and an aggregate() that rolls per-case rows into MLflow-ready numbers.
"""
from __future__ import annotations

from statistics import mean

from app.chat.prompt import all_citation_markers


# --- retrieval metrics (retrieved/expected are document-title lists; retrieved is rank order) ---

def hit_at_k(retrieved: list[str], expected: list[str], k: int) -> float:
    top = retrieved[:k]
    return 1.0 if any(e in top for e in expected) else 0.0


def recall_at_k(retrieved: list[str], expected: list[str], k: int) -> float:
    exp = set(expected)
    if not exp:
        return 0.0
    top = set(retrieved[:k])
    return sum(1 for e in exp if e in top) / len(exp)


def mrr(retrieved: list[str], expected: list[str]) -> float:
    exp = set(expected)
    for i, r in enumerate(retrieved, start=1):
        if r in exp:
            return 1.0 / i
    return 0.0


# --- answer-quality metrics (over the generated answer text) ---

def extract_markers(answer: str) -> list[int]:
    return all_citation_markers(answer)


def citation_validity(answer: str, n_context: int) -> float:
    """Fraction of the markers the answer emitted that point at a real context item. No markers
    → 1.0 (nothing hallucinated). Catches an LLM citing [9] when only 5 items were given."""
    markers = extract_markers(answer)
    if not markers:
        return 1.0
    return sum(1 for m in markers if 1 <= m <= n_context) / len(markers)


def keyword_recall(answer: str, keywords: list[str]) -> float:
    """Fraction of expected keyword substrings present in the answer (case-insensitive)."""
    if not keywords:
        return 1.0
    low = answer.lower()
    return sum(1 for kw in keywords if kw.lower() in low) / len(keywords)


def is_refusal(answer: str, refusal_texts: list[str]) -> bool:
    low = answer.strip().lower()
    return any(rt.strip().lower() in low for rt in refusal_texts if rt.strip())


def refusal_correct(answer: str, expect_refusal: bool, refusal_texts: list[str]) -> bool:
    return is_refusal(answer, refusal_texts) == expect_refusal


# --- latency + aggregation ---

def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    rank = (p / 100.0) * (len(s) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(s) - 1)
    return float(s[lo] + (s[hi] - s[lo]) * (rank - lo))


def _mean_skip_none(values) -> float | None:
    nums = [v for v in values if v is not None]
    return float(mean(nums)) if nums else None


def aggregate(rows: list[dict]) -> dict:
    """Roll per-case rows into aggregate metrics. Each row may carry: hit, recall, mrr,
    citation_validity, keyword_recall (floats or None when N/A), refusal_correct (bool),
    expected_refusal (bool, ground-truth label), is_refusal (bool, model's actual behaviour),
    latency_ms (float). Returns only numeric values (MLflow-ready)."""
    lat = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
    refusal_flags = [1.0 if r["refusal_correct"] else 0.0 for r in rows if "refusal_correct" in r]
    agg: dict[str, float | int | None] = {
        "n_cases": len(rows),
        # count refusal *cases* by ground-truth label (stable); is_refusal is the model's behaviour
        "n_refusal_cases": sum(1 for r in rows if r.get("expected_refusal")),
        "n_refused_by_model": sum(1 for r in rows if r.get("is_refusal")),
        "hit_at_k": _mean_skip_none(r.get("hit") for r in rows),
        "recall_at_k": _mean_skip_none(r.get("recall") for r in rows),
        "mrr": _mean_skip_none(r.get("mrr") for r in rows),
        "citation_validity": _mean_skip_none(r.get("citation_validity") for r in rows),
        "keyword_recall": _mean_skip_none(r.get("keyword_recall") for r in rows),
        "refusal_accuracy": float(mean(refusal_flags)) if refusal_flags else None,
        "latency_p50_ms": percentile(lat, 50),
        "latency_p95_ms": percentile(lat, 95),
        "latency_mean_ms": float(mean(lat)) if lat else 0.0,
    }
    return {k: v for k, v in agg.items() if v is not None}
