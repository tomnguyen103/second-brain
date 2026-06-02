"""Eval harness — run the RAG pipeline over the dataset for one config (ADR-0008).

Per case: retrieve+generate (read-only `answer_question`), then score retrieval (hit/recall/MRR
at document granularity) and the answer (citation validity, keyword recall, refusal). Retrieval
metrics are N/A (None) for the deliberate refusal case. Returns an EvalReport with per-case rows
and the aggregate.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.chat.prompt import PROMPTS
from app.config import Settings
from app.eval import metrics
from app.eval.configs import EvalConfig, settings_for
from app.eval.dataset import EvalCase
from app.eval.pipeline import answer_question
from app.llm.factory import get_llm_client

# A model "refused" if its answer matches any known refusal phrasing (version-independent).
_REFUSAL_TEXTS = [spec.refusal_text for spec in PROMPTS.values()]


@dataclass
class EvalReport:
    config: EvalConfig
    rows: list[dict]
    aggregate: dict


def run_eval(db: Session, embedder, dataset: list[EvalCase], config: EvalConfig,
             *, settings: Settings | None = None, llm=None) -> EvalReport:
    cfg_settings = settings_for(config, base=settings)
    client = llm if llm is not None else get_llm_client(cfg_settings)

    rows: list[dict] = []
    for case in dataset:
        result = answer_question(db, embedder, client, cfg_settings, case.question,
                                 top_k=config.top_k)
        if case.expect_refusal:
            hit = recall = reciprocal = None        # retrieval metrics N/A for the refusal case
            keyword = None
        else:
            hit = metrics.hit_at_k(result.retrieved_docs, case.expected_docs, config.top_k)
            recall = metrics.recall_at_k(result.retrieved_docs, case.expected_docs, config.top_k)
            reciprocal = metrics.mrr(result.retrieved_docs, case.expected_docs)
            keyword = metrics.keyword_recall(result.answer, case.expected_keywords)
        rows.append({
            "id": case.id,
            "question": case.question,
            "expected_docs": case.expected_docs,
            "retrieved_docs": result.retrieved_docs,
            "answer": result.answer,
            "n_context": result.n_context,
            "hit": hit,
            "recall": recall,
            "mrr": reciprocal,
            "citation_validity": metrics.citation_validity(result.answer, result.n_context),
            "keyword_recall": keyword,
            "refusal_correct": metrics.refusal_correct(
                result.answer, case.expect_refusal, _REFUSAL_TEXTS),
            "is_refusal": case.expect_refusal,
            "latency_ms": float(result.latency_ms),
            "model": result.model,
        })

    return EvalReport(config=config, rows=rows, aggregate=metrics.aggregate(rows))
