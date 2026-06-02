"""Eval harness end-to-end over a real DB (ADR-0008). Deterministic: fake embedder + fake LLM."""
import os

import pytest

from app.eval.configs import CONFIGS
from app.eval.dataset import load_corpus, load_dataset
from app.eval.harness import run_eval
from app.ingest.service import DocumentInput, SourceSpec, ingest_documents
from app.llm.fake import FakeLLMClient

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB")


def _ingest_corpus(db, embedder):
    docs = [DocumentInput(title=d.title, content=d.content) for d in load_corpus()]
    ingest_documents(db, embedder, source=SourceSpec(type="manual", name="Eval Corpus"),
                     documents=docs)


def test_harness_runs_and_scores(db_session, fake_embedder):
    _ingest_corpus(db_session, fake_embedder)
    dataset = load_dataset()

    report = run_eval(db_session, fake_embedder, dataset, CONFIGS["baseline"],
                      llm=FakeLLMClient())

    # one row per case, with all metric keys
    assert len(report.rows) == len(dataset)
    for row in report.rows:
        assert {"hit", "recall", "mrr", "citation_validity", "keyword_recall",
                "refusal_correct", "is_refusal", "latency_ms"} <= set(row)

    # non-refusal rows have in-range retrieval metrics; refusal row has them as None
    non_refusal = [r for r in report.rows if not r["is_refusal"]]
    refusal = [r for r in report.rows if r["is_refusal"]]
    assert len(refusal) == 1
    assert refusal[0]["hit"] is None
    for r in non_refusal:
        assert r["hit"] in (0.0, 1.0)
        assert 0.0 <= r["recall"] <= 1.0
        assert 0.0 <= r["mrr"] <= 1.0

    # retrieval actually works end-to-end: full-text carries relevance even with the fake
    # embedder, so at least some expected docs are retrieved.
    agg = report.aggregate
    assert agg["n_cases"] == len(dataset)
    assert agg["n_refusal_cases"] == 1
    assert agg["hit_at_k"] > 0.0
    assert "latency_p50_ms" in agg and "refusal_accuracy" in agg
    assert all(isinstance(v, (int, float)) for v in agg.values())


def test_harness_variant_config_uses_v2(db_session, fake_embedder):
    """The variant config (rag-v2, top_k=8) runs and produces a full report too."""
    _ingest_corpus(db_session, fake_embedder)
    report = run_eval(db_session, fake_embedder, load_dataset(), CONFIGS["variant"],
                      llm=FakeLLMClient())
    assert report.config.prompt_version == "rag-v2"
    assert len(report.rows) >= 12
