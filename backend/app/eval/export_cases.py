"""Export reviewed Postgres eval cases as a source-controlled YAML patch fragment.

The production promotion endpoint writes `eval_cases` rows. This module gives an operator a
reviewable bridge back to `backend/eval/dataset.yaml` without letting the API mutate repo files.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EvalCaseRecord
from app.eval.dataset import (
    CORPUS_DIR,
    DEFAULT_DATASET,
    EvalCase,
    load_dataset,
    validate_new_eval_case,
)


def _case_item(case: EvalCase) -> dict:
    item = {
        "id": case.id,
        "question": case.question,
        "expected_docs": case.expected_docs,
        "expected_keywords": case.expected_keywords,
        "expect_refusal": case.expect_refusal,
    }
    if case.review:
        item["review"] = case.review
    return item


def record_to_eval_case(record: EvalCaseRecord) -> EvalCase:
    return EvalCase(
        id=record.case_id,
        question=record.question,
        expected_docs=list(record.expected_docs or []),
        expected_keywords=list(record.expected_keywords or []),
        expect_refusal=record.expect_refusal,
        review=dict(record.review or {}),
    )


def load_export_records(db: Session, *, case_ids: Sequence[str] | None = None) -> list[EvalCaseRecord]:
    stmt = select(EvalCaseRecord).order_by(EvalCaseRecord.id)
    if case_ids:
        stmt = stmt.where(EvalCaseRecord.case_id.in_(list(case_ids)))
    return list(db.scalars(stmt).all())


def export_cases_fragment(
    records: Iterable[EvalCaseRecord],
    *,
    dataset_path: Path | str = DEFAULT_DATASET,
    corpus_dir: Path | str | None = CORPUS_DIR,
) -> str:
    """Return a `cases:` YAML fragment for staged rows not already in the fixed dataset."""
    fixed_ids = {case.id for case in load_dataset(dataset_path, corpus_dir=corpus_dir)}
    seen = set(fixed_ids)
    cases: list[EvalCase] = []
    for record in records:
        if record.case_id in fixed_ids:
            continue
        case = validate_new_eval_case(
            record_to_eval_case(record),
            existing_ids=seen,
            corpus_dir=corpus_dir,
        )
        seen.add(case.id)
        cases.append(case)

    return yaml.safe_dump(
        {"cases": [_case_item(case) for case in cases]},
        sort_keys=False,
        allow_unicode=False,
    )


def export_cases_from_db(
    db: Session,
    *,
    case_ids: Sequence[str] | None = None,
    dataset_path: Path | str = DEFAULT_DATASET,
    corpus_dir: Path | str | None = CORPUS_DIR,
) -> str:
    records = load_export_records(db, case_ids=case_ids)
    return export_cases_fragment(records, dataset_path=dataset_path, corpus_dir=corpus_dir)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.eval.export_cases",
        description="Export durable eval_cases rows as a reviewed YAML fragment.",
    )
    parser.add_argument("--case-id", action="append", dest="case_ids", help="export one case id")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="fixed eval dataset path")
    parser.add_argument("--corpus", default=str(CORPUS_DIR), help="fixed eval corpus directory")
    parser.add_argument(
        "--output",
        default="-",
        help="output file path; '-' writes to stdout",
    )
    args = parser.parse_args(argv)

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        fragment = export_cases_from_db(
            db,
            case_ids=args.case_ids,
            dataset_path=Path(args.dataset),
            corpus_dir=Path(args.corpus),
        )

    if args.output == "-":
        print(fragment, end="")
    else:
        Path(args.output).write_text(fragment, encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI boundary
    raise SystemExit(main())
