"""Eval dataset + corpus loader (ADR-0008). DB-free."""
import pytest

from app.eval.dataset import (
    EvalCase,
    append_eval_case,
    load_corpus,
    load_dataset,
)


def test_corpus_loads_with_titles():
    docs = load_corpus()
    titles = {d.title for d in docs}
    assert len(docs) >= 6
    # H1 titles the dataset references
    assert {
        "HNSW index tuning",
        "Reciprocal rank fusion",
        "Postgres full-text search",
        "Docker Compose runtime",
        "FastAPI backend",
        "MiniLM embeddings",
    } <= titles
    assert all(d.content.strip() for d in docs)


def test_dataset_loads_and_is_consistent():
    cases = load_dataset()
    assert len(cases) >= 12
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids)), "case ids must be unique"

    refusals = [c for c in cases if c.expect_refusal]
    assert len(refusals) >= 3
    assert all(c.expected_docs == [] for c in refusals)
    assert all(c.expected_keywords == [] for c in refusals)

    corpus_titles = {d.title for d in load_corpus()}
    for c in cases:
        for doc in c.expected_docs:
            assert doc in corpus_titles, f"case {c.id} references unknown doc {doc!r}"

    assert any(len(c.expected_docs) >= 2 for c in cases)


def test_explicit_reviewed_keys_are_required(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text("cases:\n  - id: a\n    question: q?\n    expected_docs: ['X']\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required keys"):
        load_dataset(p, corpus_dir=None)


def test_valid_custom_dataset_can_skip_corpus_validation(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text(
        "cases:\n"
        "  - id: a\n"
        "    question: q?\n"
        "    expected_docs: ['X']\n"
        "    expected_keywords: []\n"
        "    expect_refusal: false\n",
        encoding="utf-8",
    )
    cases = load_dataset(p, corpus_dir=None)
    assert cases == [
        EvalCase(
            id="a",
            question="q?",
            expected_docs=["X"],
            expected_keywords=[],
            expect_refusal=False,
        )
    ]


def test_unknown_keys_rejected(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text(
        "cases:\n"
        "  - id: a\n"
        "    question: q?\n"
        "    expected_docs: ['X']\n"
        "    expected_keywords: []\n"
        "    expect_refusal: false\n"
        "    metadata: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown keys"):
        load_dataset(p, corpus_dir=None)


def test_review_provenance_loads_when_valid(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text(
        "cases:\n"
        "  - id: a\n"
        "    question: q?\n"
        "    expected_docs: ['X']\n"
        "    expected_keywords: []\n"
        "    expect_refusal: false\n"
        "    review:\n"
        "      source: feedback\n"
        "      feedback_id: 123\n"
        "      reviewed_at: '2026-06-05T11:00:00+00:00'\n"
        "      reviewed_by: eval-reviewer\n"
        "      confirmations:\n"
        "        expected_docs: true\n"
        "        expected_keywords: true\n"
        "        expect_refusal: true\n",
        encoding="utf-8",
    )

    cases = load_dataset(p, corpus_dir=None)

    assert cases[0].review["source"] == "feedback"
    assert cases[0].review["feedback_id"] == 123
    assert cases[0].review["confirmations"] == {
        "expect_refusal": True,
        "expected_docs": True,
        "expected_keywords": True,
    }


def test_review_provenance_is_strict(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text(
        "cases:\n"
        "  - id: a\n"
        "    question: q?\n"
        "    expected_docs: ['X']\n"
        "    expected_keywords: []\n"
        "    expect_refusal: false\n"
        "    review:\n"
        "      source: feedback\n"
        "      feedback_id: 123\n"
        "      reviewed_at: '2026-06-05T11:00:00+00:00'\n"
        "      reviewed_by: eval-reviewer\n"
        "      confirmations:\n"
        "        expected_docs: true\n"
        "        expected_keywords: false\n"
        "        expect_refusal: true\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expected_keywords must be true"):
        load_dataset(p, corpus_dir=None)


def test_duplicate_id_rejected(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text(
        "cases:\n"
        "  - {id: a, question: q1, expected_docs: ['X'], expected_keywords: [], expect_refusal: false}\n"
        "  - {id: a, question: q2, expected_docs: ['Y'], expected_keywords: [], expect_refusal: false}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_dataset(p, corpus_dir=None)


def test_non_refusal_requires_expected_docs(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text(
        "cases:\n"
        "  - {id: a, question: 'q?', expected_docs: [], expected_keywords: [], expect_refusal: false}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expected_docs"):
        load_dataset(p, corpus_dir=None)


def test_refusal_requires_empty_docs_and_keywords(tmp_path):
    p = tmp_path / "d.yaml"
    p.write_text(
        "cases:\n"
        "  - {id: a, question: 'q?', expected_docs: [], expected_keywords: ['no'], expect_refusal: true}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expected_keywords"):
        load_dataset(p, corpus_dir=None)


def test_expected_docs_must_exist_in_corpus(tmp_path):
    dataset = tmp_path / "d.yaml"
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "ok.md").write_text("# Known doc\nbody\n", encoding="utf-8")
    dataset.write_text(
        "cases:\n"
        "  - id: a\n"
        "    question: q?\n"
        "    expected_docs: ['Missing doc']\n"
        "    expected_keywords: []\n"
        "    expect_refusal: false\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not in the eval corpus"):
        load_dataset(dataset, corpus_dir=corpus)


def test_append_eval_case_validates_before_writing(tmp_path):
    dataset = tmp_path / "d.yaml"
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "known.md").write_text("# Known doc\nbody\n", encoding="utf-8")
    dataset.write_text("cases: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not in the eval corpus"):
        append_eval_case(
            EvalCase(
                id="bad",
                question="q?",
                expected_docs=["Missing doc"],
                expected_keywords=[],
                expect_refusal=False,
            ),
            path=dataset,
            corpus_dir=corpus,
        )
    assert dataset.read_text(encoding="utf-8") == "cases: []\n"

    reviewed = append_eval_case(
        EvalCase(
            id="good",
            question="What is known?",
            expected_docs=["Known doc"],
            expected_keywords=["known"],
            expect_refusal=False,
            review={
                "source": "feedback",
                "feedback_id": 123,
                "reviewed_at": "2026-06-05T11:00:00+00:00",
                "reviewed_by": "eval-reviewer",
                "confirmations": {
                    "expected_docs": True,
                    "expected_keywords": True,
                    "expect_refusal": True,
                },
            },
        ),
        path=dataset,
        corpus_dir=corpus,
    )
    assert reviewed.id == "good"
    assert reviewed.review["feedback_id"] == 123
    assert load_dataset(dataset, corpus_dir=corpus) == [reviewed]
