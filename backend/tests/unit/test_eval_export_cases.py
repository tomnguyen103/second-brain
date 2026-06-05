from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.eval.export_cases import export_cases_fragment, record_to_eval_case


def _review(feedback_id: int = 1) -> dict:
    return {
        "source": "feedback",
        "feedback_id": feedback_id,
        "reviewed_at": "2026-06-05T12:00:00+00:00",
        "reviewed_by": "eval-reviewer",
        "confirmations": {
            "expected_docs": True,
            "expected_keywords": True,
            "expect_refusal": True,
        },
    }


def _record(case_id: str, *, feedback_id: int = 1):
    return SimpleNamespace(
        case_id=case_id,
        question="What should feedback review prove?",
        expected_docs=["Feedback analytics doc"],
        expected_keywords=["feedback"],
        expect_refusal=False,
        review=_review(feedback_id),
    )


def test_record_to_eval_case_preserves_reviewed_fields():
    case = record_to_eval_case(_record("feedback-1-reviewed"))

    assert case.id == "feedback-1-reviewed"
    assert case.expected_docs == ["Feedback analytics doc"]
    assert case.expected_keywords == ["feedback"]
    assert case.review["feedback_id"] == 1


def test_export_cases_fragment_skips_cases_already_in_fixed_dataset(tmp_path):
    dataset = tmp_path / "dataset.yaml"
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "feedback.md").write_text("# Feedback analytics doc\nbody\n", encoding="utf-8")
    dataset.write_text(
        "cases:\n"
        "  - id: already-fixed\n"
        "    question: Existing?\n"
        "    expected_docs:\n"
        "      - Feedback analytics doc\n"
        "    expected_keywords:\n"
        "      - feedback\n"
        "    expect_refusal: false\n",
        encoding="utf-8",
    )

    text = export_cases_fragment(
        [_record("already-fixed"), _record("new-reviewed", feedback_id=2)],
        dataset_path=dataset,
        corpus_dir=corpus,
    )

    assert "already-fixed" not in text
    assert "new-reviewed" in text
    assert "review:" in text
    assert "feedback_id: 2" in text


def test_export_cases_fragment_validates_against_fixed_corpus(tmp_path):
    dataset = tmp_path / "dataset.yaml"
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "other.md").write_text("# Other doc\nbody\n", encoding="utf-8")
    dataset.write_text("cases: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not in the eval corpus"):
        export_cases_fragment([_record("bad-doc")], dataset_path=dataset, corpus_dir=corpus)
