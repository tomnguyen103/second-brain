"""Eval dataset + corpus loader (ADR-0008). DB-free."""
import pytest

from app.eval.dataset import (
    CORPUS_DIR,
    DEFAULT_DATASET,
    EvalCase,
    load_corpus,
    load_dataset,
)


def test_corpus_loads_with_titles():
    docs = load_corpus()
    titles = {d.title for d in docs}
    assert len(docs) >= 6
    # H1 titles the dataset references
    assert {"HNSW index tuning", "Reciprocal rank fusion", "Postgres full-text search",
            "Docker Compose runtime", "FastAPI backend", "MiniLM embeddings"} <= titles
    assert all(d.content.strip() for d in docs)


def test_dataset_loads_and_is_consistent():
    cases = load_dataset()
    assert len(cases) >= 12
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids)), "case ids must be unique"

    # deliberate refusal cases have no expected docs
    refusals = [c for c in cases if c.expect_refusal]
    assert len(refusals) >= 3
    assert all(c.expected_docs == [] for c in refusals)

    # every expected_doc names a real corpus document
    corpus_titles = {d.title for d in load_corpus()}
    for c in cases:
        for doc in c.expected_docs:
            assert doc in corpus_titles, f"case {c.id} references unknown doc {doc!r}"

    # at least one multi-source case exercises fusion
    assert any(len(c.expected_docs) >= 2 for c in cases)


def test_unknown_keys_default(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text("cases:\n  - id: a\n    question: q?\n    expected_docs: ['X']\n", encoding="utf-8")
    cases = load_dataset(p)
    assert cases == [EvalCase(id="a", question="q?", expected_docs=["X"],
                              expected_keywords=[], expect_refusal=False)]


def test_duplicate_id_rejected(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text(
        "cases:\n  - {id: a, question: q1, expected_docs: ['X']}\n"
        "  - {id: a, question: q2, expected_docs: ['Y']}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_dataset(p)


def test_non_refusal_requires_expected_docs(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text('cases:\n  - {id: a, question: "q?"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="expected_docs"):
        load_dataset(p)
