"""Eval dataset + corpus loading (ADR-0008).

The corpus is a small fixed set of markdown notes (one topic per file, title = first H1).
The dataset (YAML) is a list of cases: a question, the document(s) we expect retrieval to
surface, keyword substrings the answer should contain, and a flag for deliberate off-corpus
refusal cases. Retrieval is measured at document granularity (one topic per doc).
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# backend/app/eval/dataset.py -> parents[2] == backend/
_BACKEND = Path(__file__).resolve().parents[2]
EVAL_DIR = _BACKEND / "eval"
CORPUS_DIR = EVAL_DIR / "corpus"
DEFAULT_DATASET = EVAL_DIR / "dataset.yaml"
CASE_KEYS = {
    "id",
    "question",
    "expected_docs",
    "expected_keywords",
    "expect_refusal",
    "review",
}
REQUIRED_CASE_KEYS = CASE_KEYS - {"review"}
REVIEW_KEYS = {"source", "feedback_id", "reviewed_at", "reviewed_by", "confirmations"}
CONFIRMATION_KEYS = {"expected_docs", "expected_keywords", "expect_refusal"}


@dataclass
class CorpusDoc:
    title: str
    content: str


@dataclass
class EvalCase:
    id: str
    question: str
    expected_docs: list[str] = field(default_factory=list)     # document titles, rank-agnostic
    expected_keywords: list[str] = field(default_factory=list)  # substrings expected in the answer
    expect_refusal: bool = False                                # off-corpus -> should refuse
    review: dict[str, Any] = field(default_factory=dict)         # optional reviewer provenance


def load_corpus(corpus_dir: Path | str = CORPUS_DIR) -> list[CorpusDoc]:
    docs: list[CorpusDoc] = []
    for path in sorted(Path(corpus_dir).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        first = text.splitlines()[0].strip() if text.strip() else ""
        title = first[2:].strip() if first.startswith("# ") else path.stem
        docs.append(CorpusDoc(title=title, content=text))
    return docs


def _string_list(value: Any, *, field_name: str, cid: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"case {cid}: {field_name} must be a list")
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"case {cid}: {field_name} entries must be non-empty strings")
        normalized = item.strip()
        if normalized in seen:
            raise ValueError(f"case {cid}: duplicate {field_name} entry {normalized!r}")
        seen.add(normalized)
        out.append(normalized)
    return out


def _corpus_titles(corpus_dir: Path | str | None) -> set[str] | None:
    if corpus_dir is None:
        return None
    return {doc.title for doc in load_corpus(corpus_dir)}


def _case_from_item(
    item: Mapping[str, Any], *, seen: set[str], corpus_titles: set[str] | None
) -> EvalCase:
    unknown = set(item) - CASE_KEYS
    if unknown:
        raise ValueError(f"case has unknown keys: {sorted(unknown)}")

    missing = REQUIRED_CASE_KEYS - set(item)
    if missing:
        label = item.get("id", "<missing id>")
        raise ValueError(f"case {label}: missing required keys: {sorted(missing)}")

    raw_id = item["id"]
    if not isinstance(raw_id, str) or not raw_id.strip():
        raise ValueError("case id must be a non-empty string")
    cid = raw_id.strip()
    if cid in seen:
        raise ValueError(f"duplicate eval case id: {cid}")
    seen.add(cid)

    question = item["question"]
    if not isinstance(question, str) or not question.strip():
        raise ValueError(f"case {cid}: question must be a non-empty string")

    expect_refusal = item["expect_refusal"]
    if not isinstance(expect_refusal, bool):
        raise ValueError(f"case {cid}: expect_refusal must be a boolean")

    expected_docs = _string_list(item["expected_docs"], field_name="expected_docs", cid=cid)
    expected_keywords = _string_list(
        item["expected_keywords"], field_name="expected_keywords", cid=cid
    )

    if not expect_refusal and not expected_docs:
        raise ValueError(f"case {cid}: a non-refusal case must name expected_docs")
    if expect_refusal and expected_docs:
        raise ValueError(f"case {cid}: a refusal case must not name expected_docs")
    if expect_refusal and expected_keywords:
        raise ValueError(f"case {cid}: a refusal case must not name expected_keywords")

    if corpus_titles is not None:
        for doc in expected_docs:
            if doc not in corpus_titles:
                raise ValueError(f"case {cid}: expected_doc {doc!r} is not in the eval corpus")

    review = _review_from_item(item.get("review"), cid=cid)

    return EvalCase(
        id=cid,
        question=question.strip(),
        expected_docs=expected_docs,
        expected_keywords=expected_keywords,
        expect_refusal=expect_refusal,
        review=review,
    )


def _review_from_item(value: Any, *, cid: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"case {cid}: review must be a mapping")

    unknown = set(value) - REVIEW_KEYS
    if unknown:
        raise ValueError(f"case {cid}: review has unknown keys: {sorted(unknown)}")

    missing = REVIEW_KEYS - set(value)
    if missing:
        raise ValueError(f"case {cid}: review missing required keys: {sorted(missing)}")

    source = value["source"]
    if not isinstance(source, str) or source != "feedback":
        raise ValueError(f"case {cid}: review.source must be 'feedback'")

    feedback_id = value["feedback_id"]
    if not isinstance(feedback_id, int) or isinstance(feedback_id, bool) or feedback_id <= 0:
        raise ValueError(f"case {cid}: review.feedback_id must be a positive integer")

    reviewed_at = value["reviewed_at"]
    if not isinstance(reviewed_at, str) or not reviewed_at.strip():
        raise ValueError(f"case {cid}: review.reviewed_at must be a non-empty string")

    reviewed_by = value["reviewed_by"]
    if not isinstance(reviewed_by, str) or not reviewed_by.strip():
        raise ValueError(f"case {cid}: review.reviewed_by must be a non-empty string")

    confirmations = value["confirmations"]
    if not isinstance(confirmations, Mapping):
        raise ValueError(f"case {cid}: review.confirmations must be a mapping")
    unknown_confirmations = set(confirmations) - CONFIRMATION_KEYS
    if unknown_confirmations:
        raise ValueError(
            f"case {cid}: review.confirmations has unknown keys: "
            f"{sorted(unknown_confirmations)}"
        )
    missing_confirmations = CONFIRMATION_KEYS - set(confirmations)
    if missing_confirmations:
        raise ValueError(
            f"case {cid}: review.confirmations missing required keys: "
            f"{sorted(missing_confirmations)}"
        )
    reviewed_confirmations: dict[str, bool] = {}
    for key in sorted(CONFIRMATION_KEYS):
        confirmed = confirmations[key]
        if not isinstance(confirmed, bool):
            raise ValueError(f"case {cid}: review.confirmations.{key} must be a boolean")
        if not confirmed:
            raise ValueError(f"case {cid}: review.confirmations.{key} must be true")
        reviewed_confirmations[key] = confirmed

    return {
        "source": source,
        "feedback_id": feedback_id,
        "reviewed_at": reviewed_at.strip(),
        "reviewed_by": reviewed_by.strip(),
        "confirmations": reviewed_confirmations,
    }


def _parse_dataset(raw: Any, *, corpus_titles: set[str] | None) -> list[EvalCase]:
    if not isinstance(raw, dict):
        raise ValueError("eval dataset must be a mapping with a cases list")
    unknown = set(raw) - {"cases"}
    if unknown:
        raise ValueError(f"eval dataset has unknown top-level keys: {sorted(unknown)}")
    items = raw.get("cases")
    if not isinstance(items, list):
        raise ValueError("eval dataset cases must be a list")

    cases: list[EvalCase] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("eval case entries must be mappings")
        cases.append(_case_from_item(item, seen=seen, corpus_titles=corpus_titles))
    return cases


def load_dataset(
    path: Path | str = DEFAULT_DATASET, *, corpus_dir: Path | str | None = CORPUS_DIR
) -> list[EvalCase]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return _parse_dataset(raw, corpus_titles=_corpus_titles(corpus_dir))


def _case_item(case: EvalCase) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": case.id,
        "question": case.question,
        "expected_docs": case.expected_docs,
        "expected_keywords": case.expected_keywords,
        "expect_refusal": case.expect_refusal,
    }
    if case.review:
        item["review"] = case.review
    return item


def _case_block(case: EvalCase) -> str:
    dumped = yaml.safe_dump([_case_item(case)], sort_keys=False, allow_unicode=False).rstrip()
    return "\n" + "\n".join(f"  {line}" for line in dumped.splitlines()) + "\n"


def append_eval_case(
    case: EvalCase,
    *,
    path: Path | str = DEFAULT_DATASET,
    corpus_dir: Path | str | None = CORPUS_DIR,
) -> EvalCase:
    dataset_path = Path(path)
    current_text = dataset_path.read_text(encoding="utf-8")
    existing = load_dataset(dataset_path, corpus_dir=corpus_dir)
    reviewed = validate_new_eval_case(
        case,
        existing_ids={item.id for item in existing},
        corpus_dir=corpus_dir,
    )

    base_text = current_text.rstrip()
    if base_text.endswith("cases: []"):
        base_text = base_text[: -len("cases: []")] + "cases:"
    new_text = base_text + _case_block(reviewed)
    _parse_dataset(yaml.safe_load(new_text), corpus_titles=_corpus_titles(corpus_dir))
    dataset_path.write_text(new_text, encoding="utf-8")
    return reviewed


def validate_new_eval_case(
    case: EvalCase,
    *,
    existing_ids: set[str] | None = None,
    corpus_dir: Path | str | None = CORPUS_DIR,
) -> EvalCase:
    """Validate a candidate case against the fixed corpus without writing a dataset file."""
    return _case_from_item(
        _case_item(case),
        seen=set(existing_ids or set()),
        corpus_titles=_corpus_titles(corpus_dir),
    )
