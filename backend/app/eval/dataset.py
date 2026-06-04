"""Eval dataset + corpus loading (ADR-0008).

The corpus is a small fixed set of markdown notes (one topic per file, title = first H1).
The dataset (YAML) is a list of cases: a question, the document(s) we expect retrieval to
surface, keyword substrings the answer should contain, and a flag for deliberate off-corpus
refusal cases. Retrieval is measured at *document* granularity (one topic per doc).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

# backend/app/eval/dataset.py → parents[2] == backend/
_BACKEND = Path(__file__).resolve().parents[2]
EVAL_DIR = _BACKEND / "eval"
CORPUS_DIR = EVAL_DIR / "corpus"
DEFAULT_DATASET = EVAL_DIR / "dataset.yaml"


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
    expect_refusal: bool = False                                # off-corpus → should refuse


def load_corpus(corpus_dir: Path | str = CORPUS_DIR) -> list[CorpusDoc]:
    docs: list[CorpusDoc] = []
    for path in sorted(Path(corpus_dir).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        first = text.splitlines()[0].strip() if text.strip() else ""
        title = first[2:].strip() if first.startswith("# ") else path.stem
        docs.append(CorpusDoc(title=title, content=text))
    return docs


def load_dataset(path: Path | str = DEFAULT_DATASET) -> list[EvalCase]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    items = raw["cases"] if isinstance(raw, dict) else raw
    cases: list[EvalCase] = []
    seen: set[str] = set()
    for item in items:
        cid = str(item["id"])
        if cid in seen:
            raise ValueError(f"duplicate eval case id: {cid}")
        seen.add(cid)
        case = EvalCase(
            id=cid,
            question=item["question"],
            expected_docs=list(item.get("expected_docs", [])),
            expected_keywords=list(item.get("expected_keywords", [])),
            expect_refusal=bool(item.get("expect_refusal", False)),
        )
        if not case.expect_refusal and not case.expected_docs:
            raise ValueError(f"case {cid}: a non-refusal case must name expected_docs")
        if case.expect_refusal and case.expected_docs:
            raise ValueError(f"case {cid}: a refusal case must not name expected_docs")
        cases.append(case)
    return cases
