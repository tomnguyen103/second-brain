"""Optional query rewrite hook for retrieval."""
from __future__ import annotations

from app.config import Settings
from app.llm.base import LLMMessage


def _clean_rewrite(text: str, max_chars: int) -> str:
    cleaned = " ".join((text or "").strip().split())
    if not cleaned:
        return ""
    if cleaned.startswith(("'", '"')) and cleaned.endswith(("'", '"')):
        cleaned = cleaned[1:-1].strip()
    return cleaned[:max_chars].strip()


def maybe_rewrite_query(llm, settings: Settings, query: str) -> tuple[str, dict]:
    """Return the retrieval query plus metadata.

    Disabled by default. When enabled, failures fall back to the original query so an optional
    quality hook cannot break chat/eval availability.
    """
    meta = {
        "query_rewrite_enabled": settings.retrieval_query_rewrite_enabled,
        "query_rewritten": False,
    }
    if not settings.retrieval_query_rewrite_enabled:
        return query, meta

    messages = [
        LLMMessage(
            "system",
            "Rewrite user questions into concise search queries for personal notes. "
            "Return only the rewritten query, with no explanation.",
        ),
        LLMMessage("user", query),
    ]
    try:
        resp = llm.generate(messages)
    except Exception as exc:  # pragma: no cover - provider-specific network failures
        return query, {**meta, "query_rewrite_failed": type(exc).__name__}

    rewritten = _clean_rewrite(resp.text, settings.retrieval_query_rewrite_max_chars)
    if not rewritten or rewritten.lower() == query.strip().lower():
        return query, meta
    return rewritten, {**meta, "query_rewritten": True}
