"""LangGraph-backed read-only agentic RAG orchestration.

V1 stays deliberately bounded: plan subqueries, search existing notes, optionally retry the
original question when evidence is weak, then answer through the same citation validator used by
regular chat. It does not call mutation tools, fetch the web, or persist graph checkpoints.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.chat.prompt import ContextItem, build_messages, get_prompt
from app.chat.service import (
    ChatResult,
    _PreparedChat,
    _finalize_chat,
    _history,
    _repair_citations_if_needed,
)
from app.config import Settings
from app.db.models import Conversation, Message
from app.llm.base import LLMMessage
from app.retrieval.fusion import FusedHit
from app.retrieval.hybrid import DisplayChunk, hybrid_search, load_display_chunks

_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s*")
_FENCED_JSON_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


@dataclass
class _SubqueryResult:
    query: str
    hits: list[FusedHit]
    meta: dict


@dataclass
class AgenticAnswerResult:
    answer: str
    hits: list[FusedHit]
    display: dict[int, DisplayChunk]
    n_context: int
    latency_ms: int
    model: str | None
    usage: dict
    retrieval: dict
    messages: list[LLMMessage]


class _AgenticState(TypedDict, total=False):
    question: str
    history: list[LLMMessage]
    subqueries: list[str]
    subquery_results: list[_SubqueryResult]
    hits: list[FusedHit]
    display: dict[int, DisplayChunk]
    messages: list[LLMMessage]
    meta: dict
    answer: str
    model: str | None
    usage: dict
    latency_ms: int
    planner_failed: bool
    verifier_used: bool
    verifier_retry: bool
    fallback_used: bool
    weak_evidence: bool


def _clean_query(text: str, max_chars: int) -> str:
    cleaned = " ".join((text or "").strip().split())
    cleaned = _BULLET_RE.sub("", cleaned).strip()
    if cleaned.startswith(("'", '"')) and cleaned.endswith(("'", '"')):
        cleaned = cleaned[1:-1].strip()
    return cleaned[:max_chars].strip()


def _dedupe_queries(queries: list[str], *, max_queries: int, max_chars: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for query in queries:
        cleaned = _clean_query(query, max_chars)
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
        if len(out) >= max_queries:
            break
    return out


def _queries_from_json(value) -> list[str]:  # noqa: ANN001 - defensive JSON parser
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    if isinstance(value, dict):
        queries = value.get("queries")
        if isinstance(queries, list):
            return [str(item) for item in queries if isinstance(item, str)]
    return []


def _planner_json_candidates(text: str) -> list[str]:
    candidates = [(text or "").strip()]
    fence_match = _FENCED_JSON_RE.match(candidates[0])
    if fence_match:
        candidates.append(fence_match.group(1).strip())
    start = candidates[0].find("{")
    end = candidates[0].rfind("}")
    if 0 <= start < end:
        candidates.append(candidates[0][start:end + 1])
    return [candidate for candidate in candidates if candidate]


def parse_query_plan(text: str, *, question: str, max_queries: int, max_chars: int
                     ) -> tuple[list[str], bool]:
    """Parse planner output into bounded search queries.

    Returns `(queries, failed)`. When parsing fails or produces fewer than two queries, the
    original question is included as a conservative fallback query.
    """
    raw_queries: list[str] = []
    failed = False
    for candidate in _planner_json_candidates(text):
        try:
            raw_queries = _queries_from_json(json.loads(candidate))
        except json.JSONDecodeError:
            continue
        if raw_queries:
            break
    else:
        raw_queries = [
            line for line in (text or "").splitlines()
            if _clean_query(line, max_chars)
        ]
        failed = True

    queries = _dedupe_queries(raw_queries, max_queries=max_queries, max_chars=max_chars)
    if len(queries) < 2:
        queries = _dedupe_queries([*queries, question], max_queries=max_queries,
                                  max_chars=max_chars)
        failed = True
    return queries or [_clean_query(question, max_chars)], failed


def _history_text(history: list[LLMMessage], max_chars: int = 1600) -> str:
    lines = [f"{m.role}: {m.content}" for m in history[-6:]]
    return "\n".join(lines)[-max_chars:] or "(none)"


def _planner_messages(question: str, history: list[LLMMessage], max_queries: int
                      ) -> list[LLMMessage]:
    return [
        LLMMessage(
            "system",
            "Generate focused search queries for a personal-notes RAG system. "
            "Return only JSON in the form {\"queries\":[\"...\"]}. "
            f"Produce 2 to {max_queries} concise queries. Do not answer the question.",
        ),
        LLMMessage(
            "user",
            "Conversation history:\n"
            f"{_history_text(history)}\n\n"
            f"Current question:\n{question}",
        ),
    ]


def _verifier_messages(question: str, subqueries: list[str]) -> list[LLMMessage]:
    return [
        LLMMessage(
            "system",
            "You are checking a read-only RAG retrieval plan. If the generated subqueries found "
            "no usable evidence, decide whether retrying the user's original wording is useful. "
            "Return exactly RETRY or REFUSE.",
        ),
        LLMMessage(
            "user",
            "Question:\n"
            f"{question}\n\n"
            "Subqueries already tried:\n"
            + "\n".join(f"- {q}" for q in subqueries),
        ),
    ]


def _merge_method(methods: set[str]) -> str:
    if "hybrid" in methods or {"vector", "fulltext"}.issubset(methods):
        return "hybrid"
    if "fulltext" in methods:
        return "fulltext"
    return "vector"


def _merge_hits(results: list[_SubqueryResult], top_k: int) -> list[FusedHit]:
    buckets: dict[int, dict] = {}
    for result in results:
        seen_in_query: set[int] = set()
        for hit in result.hits:
            bucket = buckets.setdefault(hit.chunk_id, {
                "score": 0.0,
                "support": 0,
                "methods": set(),
                "vector_score": None,
                "fulltext_score": None,
            })
            bucket["score"] += hit.score
            if hit.chunk_id not in seen_in_query:
                bucket["support"] += 1
                seen_in_query.add(hit.chunk_id)
            bucket["methods"].add(hit.method)
            if hit.vector_score is not None:
                current = bucket["vector_score"]
                bucket["vector_score"] = hit.vector_score if current is None else max(
                    current, hit.vector_score)
            if hit.fulltext_score is not None:
                current = bucket["fulltext_score"]
                bucket["fulltext_score"] = hit.fulltext_score if current is None else max(
                    current, hit.fulltext_score)

    merged: list[FusedHit] = []
    for chunk_id, bucket in buckets.items():
        support = int(bucket["support"])
        score = float(bucket["score"]) * (1.0 + 0.10 * max(0, support - 1))
        merged.append(FusedHit(
            chunk_id=chunk_id,
            score=score,
            method=_merge_method(bucket["methods"]),
            vector_score=bucket["vector_score"],
            fulltext_score=bucket["fulltext_score"],
        ))

    merged.sort(key=lambda h: (h.score, h.chunk_id), reverse=True)
    merged = merged[:top_k]
    for rank, hit in enumerate(merged, start=1):
        hit.rank = rank
    return merged


def _meta_from_results(results: list[_SubqueryResult], hits: list[FusedHit],
                       *, weak_evidence: bool) -> dict:
    candidates_vector = sum(int(r.meta.get("candidates_vector", 0)) for r in results)
    candidates_vector_raw = sum(int(r.meta.get("candidates_vector_raw", 0)) for r in results)
    candidates_fulltext = sum(int(r.meta.get("candidates_fulltext", 0)) for r in results)
    return {
        "method": "agentic_hybrid",
        "candidates_vector": candidates_vector,
        "candidates_vector_raw": candidates_vector_raw,
        "candidates_fulltext": candidates_fulltext,
        "fused_returned": len(hits),
        "weak_context": weak_evidence,
    }


def _agentic_trace(state: _AgenticState, settings: Settings) -> dict:
    results = state.get("subquery_results", [])
    return {
        "enabled": True,
        "strategy": "plan_subsearch_v1",
        "subqueries": state.get("subqueries", []),
        "subquery_hit_counts": [len(r.hits) for r in results],
        "deduped_chunks": len({h.chunk_id for r in results for h in r.hits}),
        "selected_chunks": len(state.get("hits", [])),
        "weak_evidence": bool(state.get("weak_evidence", False)),
        "planner_failed": bool(state.get("planner_failed", False)),
        "verifier_used": bool(state.get("verifier_used", False)),
        "fallback_used": bool(state.get("fallback_used", False)),
        "step_budget": {
            "max_subqueries": min(max(1, settings.agentic_rag_max_subqueries), 4),
            "recursion_limit": settings.agentic_rag_recursion_limit,
        },
    }


class _AgenticRagGraph:
    def __init__(
        self,
        db: Session,
        embedder,
        llm,
        settings: Settings,
        *,
        top_k: int | None,
        filters: dict | None,
        redis_client,
    ) -> None:
        self.db = db
        self.embedder = embedder
        self.llm = llm
        self.settings = settings
        self.top_k = top_k or settings.retrieval_top_k
        self.filters = filters or {}
        self.redis_client = redis_client
        self.max_queries = min(max(1, settings.agentic_rag_max_subqueries), 4)
        self.max_query_chars = settings.retrieval_query_rewrite_max_chars
        self.graph = self._build_graph()

    def _search(self, query: str) -> _SubqueryResult:
        hits, meta = hybrid_search(
            self.db,
            self.embedder,
            self.settings,
            query,
            top_k=self.top_k,
            source_ids=self.filters.get("source_ids"),
            tags=self.filters.get("tags"),
            redis_client=self.redis_client,
        )
        return _SubqueryResult(query=query, hits=hits, meta=meta)

    def plan_queries(self, state: _AgenticState) -> dict:
        try:
            response = self.llm.generate(
                _planner_messages(state["question"], state.get("history", []), self.max_queries)
            )
            queries, failed = parse_query_plan(
                response.text,
                question=state["question"],
                max_queries=self.max_queries,
                max_chars=self.max_query_chars,
            )
        except Exception:  # pragma: no cover - provider/network specific
            queries = [_clean_query(state["question"], self.max_query_chars)]
            failed = True
        return {"subqueries": queries, "planner_failed": failed}

    def retrieve_subqueries(self, state: _AgenticState) -> dict:
        return {"subquery_results": [self._search(q) for q in state.get("subqueries", [])]}

    def fallback_retrieve(self, state: _AgenticState) -> dict:
        original = _clean_query(state["question"], self.max_query_chars)
        tried = {q.lower() for q in state.get("subqueries", [])}
        results = list(state.get("subquery_results", []))
        subqueries = list(state.get("subqueries", []))
        if original.lower() not in tried:
            subqueries.append(original)
            results.append(self._search(original))
        return {
            "subqueries": subqueries,
            "subquery_results": results,
            "fallback_used": True,
        }

    def select_context(self, state: _AgenticState) -> dict:
        results = state.get("subquery_results", [])
        hits = _merge_hits(results, self.top_k)
        weak = len(hits) == 0
        return {
            "hits": hits,
            "weak_evidence": weak,
            "meta": _meta_from_results(results, hits, weak_evidence=weak),
        }

    def verify_evidence(self, state: _AgenticState) -> dict:
        retry = True
        try:
            response = self.llm.generate(
                _verifier_messages(state["question"], state.get("subqueries", []))
            )
            text = (response.text or "").strip().upper()
            retry = text != "REFUSE"
        except Exception:  # pragma: no cover - provider/network specific
            retry = True
        return {"verifier_used": True, "verifier_retry": retry}

    def answer(self, state: _AgenticState) -> dict:
        hits = state.get("hits", [])
        display = load_display_chunks(self.db, [h.chunk_id for h in hits])
        items = [
            ContextItem(i + 1, display[h.chunk_id].source_name,
                        display[h.chunk_id].document_title, display[h.chunk_id].content)
            for i, h in enumerate(hits)
        ]
        messages = build_messages(
            state["question"],
            items,
            state.get("history", []),
            prompt_version=self.settings.prompt_version,
        )
        started = time.perf_counter()
        response = self.llm.generate(messages)
        latency_ms = int((time.perf_counter() - started) * 1000)
        usage = {
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "total_tokens": response.total_tokens,
        }
        return {
            "display": display,
            "messages": messages,
            "answer": response.text,
            "model": response.model,
            "usage": usage,
            "latency_ms": latency_ms,
        }

    def refuse(self, state: _AgenticState) -> dict:
        return {"weak_evidence": True}

    def _route_after_select(self, state: _AgenticState) -> Literal["answer", "verify", "refuse"]:
        if state.get("hits"):
            return "answer"
        if self.settings.agentic_rag_verifier_enabled and not state.get("fallback_used"):
            return "verify"
        return "refuse"

    def _route_after_verify(self, state: _AgenticState) -> Literal["retry", "refuse"]:
        return "retry" if state.get("verifier_retry", False) else "refuse"

    def _build_graph(self):
        builder = StateGraph(_AgenticState)
        builder.add_node("plan_queries", self.plan_queries)
        builder.add_node("retrieve_subqueries", self.retrieve_subqueries)
        builder.add_node("select_context", self.select_context)
        builder.add_node("verify_evidence", self.verify_evidence)
        builder.add_node("fallback_retrieve", self.fallback_retrieve)
        builder.add_node("answer", self.answer)
        builder.add_node("refuse", self.refuse)
        builder.add_edge(START, "plan_queries")
        builder.add_edge("plan_queries", "retrieve_subqueries")
        builder.add_edge("retrieve_subqueries", "select_context")
        builder.add_conditional_edges("select_context", self._route_after_select, {
            "answer": "answer",
            "verify": "verify_evidence",
            "refuse": "refuse",
        })
        builder.add_conditional_edges("verify_evidence", self._route_after_verify, {
            "retry": "fallback_retrieve",
            "refuse": "refuse",
        })
        builder.add_edge("fallback_retrieve", "select_context")
        builder.add_edge("answer", END)
        builder.add_edge("refuse", END)
        return builder.compile()

    def invoke(self, question: str, history: list[LLMMessage]) -> _AgenticState:
        initial: _AgenticState = {"question": question, "history": history}
        return self.graph.invoke(
            initial,
            config={"recursion_limit": self.settings.agentic_rag_recursion_limit},
        )


def _persist_agentic_refusal(db: Session, conversation_id: int, settings: Settings,
                             meta: dict) -> ChatResult:
    refusal = get_prompt(settings.prompt_version).refusal_text
    assistant = Message(conversation_id=conversation_id, role="assistant",
                        content=refusal, model=None)
    db.add(assistant)
    db.commit()
    return ChatResult(
        conversation_id,
        assistant.id,
        refusal,
        [],
        {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        None,
        0,
        {**meta, "fused_returned": 0, "refusal_reason": "weak_context"},
    )


def answer_agentic_question(
    db: Session,
    embedder,
    llm,
    settings: Settings,
    question: str,
    *,
    history: list[LLMMessage] | None = None,
    top_k: int | None = None,
    filters: dict | None = None,
    redis_client=None,
) -> AgenticAnswerResult:
    """Run the agentic graph without writing chat history or retrieval rows."""
    graph = _AgenticRagGraph(
        db,
        embedder,
        llm,
        settings,
        top_k=top_k,
        filters=filters,
        redis_client=redis_client,
    )
    state = graph.invoke(question, history or [])
    trace = _agentic_trace(state, settings)
    meta = {**state.get("meta", {}), "agentic": trace}
    hits = state.get("hits", [])
    if not hits or "answer" not in state:
        return AgenticAnswerResult(
            answer=get_prompt(settings.prompt_version).refusal_text,
            hits=[],
            display={},
            n_context=0,
            latency_ms=0,
            model=None,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            retrieval={**meta, "fused_returned": 0, "refusal_reason": "weak_context"},
            messages=[],
        )
    return AgenticAnswerResult(
        answer=state["answer"],
        hits=hits,
        display=state["display"],
        n_context=len(hits),
        latency_ms=state.get("latency_ms", 0),
        model=state.get("model"),
        usage=state.get("usage", {}),
        retrieval=meta,
        messages=state.get("messages", []),
    )


def agentic_chat(
    db: Session,
    embedder,
    llm,
    settings: Settings,
    *,
    message: str,
    conversation_id: int | None = None,
    top_k: int | None = None,
    filters: dict | None = None,
    include_chunks: bool = True,
    redis_client=None,
) -> ChatResult:
    """Run a bounded read-only agentic RAG turn and persist the final assistant message."""
    if conversation_id is None:
        conversation = Conversation(title=message[:80])
        db.add(conversation)
        db.flush()
        conversation_id = conversation.id

    history = _history(db, conversation_id, settings.history_window)
    db.add(Message(conversation_id=conversation_id, role="user", content=message))
    db.flush()

    result = answer_agentic_question(
        db,
        embedder,
        llm,
        settings,
        message,
        history=history,
        top_k=top_k,
        filters=filters,
        redis_client=redis_client,
    )
    if not result.hits:
        return _persist_agentic_refusal(db, conversation_id, settings, result.retrieval)

    prepared = _PreparedChat(
        conversation_id=conversation_id,
        messages=result.messages,
        hits=result.hits,
        display=result.display,
        meta=result.retrieval,
        item_count=len(result.hits),
        include_chunks=include_chunks,
    )
    answer, model, usage, latency_ms = _repair_citations_if_needed(
        llm,
        prepared,
        answer=result.answer,
        model=result.model,
        usage=result.usage,
        latency_ms=result.latency_ms,
    )
    return _finalize_chat(
        db,
        prepared,
        answer=answer,
        model=model,
        usage=usage,
        latency_ms=latency_ms,
    )
