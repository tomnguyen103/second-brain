"""MCP server — exposes Second Brain's agentic actions as tools (Phase 4, ADR-0010).

Thin layer over the tested services: each tool opens its own DB session, builds the embedder/LLM,
calls a service, and returns a JSON-able result. Run it over stdio:

    python -m app.mcp_server

then point an MCP client (Claude Desktop config, or `mcp dev`/Inspector) at that command. The LLM
provider follows config (Gemini default; set SECOND_BRAIN_LLM_PROVIDER=fake for a keyless smoke).
"""
from __future__ import annotations

from contextlib import contextmanager

from mcp.server.fastmcp import FastMCP

from app.config import settings
from app.db.session import SessionLocal
from app.deps import get_embedder
from app.digest.service import build_digest
from app.llm.factory import get_llm_client
from app.research.service import research_topic as _research_topic
from app.retrieval.hybrid import hybrid_search, load_display_chunks
from app.tasks.service import create_task as _create_task
from app.tasks.service import list_tasks as _list_tasks

mcp = FastMCP("second-brain")


@contextmanager
def _session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _require_mcp_mutations_enabled() -> None:
    """Require an explicit opt-in before MCP tools can mutate durable personal data."""
    if not settings.mcp_enable_mutations:
        raise PermissionError(
            "MCP mutation tools are disabled. Set SECOND_BRAIN_MCP_ENABLE_MUTATIONS=true "
            "only for trusted local MCP clients."
        )


@mcp.tool()
def search_notes(query: str, top_k: int = 5) -> list[dict]:
    """Search the second brain (hybrid vector + full-text) and return the top matching chunks."""
    top_k = max(1, min(top_k, 50))   # clamp client-controlled top_k (SQL LIMIT)
    with _session() as db:
        hits, _meta = hybrid_search(db, get_embedder(), settings, query, top_k=top_k)
        display = load_display_chunks(db, [h.chunk_id for h in hits])
        out = []
        for h in hits:
            dc = display.get(h.chunk_id)
            if dc is None:
                continue
            out.append({
                "document_title": dc.document_title,
                "source_name": dc.source_name,
                "snippet": (dc.content or "")[:300],
                "score": h.score,
                "method": h.method,
            })
        return out


@mcp.tool()
def create_task(title: str, detail: str = "") -> dict:
    """Add a task to the user's task list. Returns the created task."""
    _require_mcp_mutations_enabled()
    with _session() as db:
        t = _create_task(db, title, detail or None)
        return {"id": t.id, "title": t.title, "detail": t.detail,
                "status": t.status, "created_at": t.created_at.isoformat()}


@mcp.tool()
def list_tasks(status: str = "", limit: int = 20) -> list[dict]:
    """List tasks, optionally filtered by status (open|done|cancelled)."""
    limit = max(1, min(limit, 100))   # clamp client-controlled limit (SQL LIMIT)
    with _session() as db:
        tasks = _list_tasks(db, status=status or None, limit=limit)
        return [{"id": t.id, "title": t.title, "detail": t.detail,
                 "status": t.status, "created_at": t.created_at.isoformat()} for t in tasks]


@mcp.tool()
def send_digest(limit: int = 10) -> str:
    """Compose a markdown digest of recent activity (recently added documents + counts)."""
    limit = max(1, min(limit, 100))   # clamp client-controlled limit (SQL LIMIT)
    with _session() as db:
        return build_digest(db, limit=limit)


@mcp.tool()
def research_topic(
    topic: str,
    source_urls: list[str] | None = None,
    source_texts: list[str] | None = None,
) -> dict:
    """Research a topic from optional public URLs or provided source text, store it as a
    source-backed research note, and auto-index it so it becomes permanently searchable."""
    _require_mcp_mutations_enabled()
    with _session() as db:
        res = _research_topic(
            db,
            get_embedder(),
            get_llm_client(settings),
            topic,
            source_urls=source_urls,
            source_texts=source_texts,
        )
        return {
            "topic": res.topic,
            "document_id": res.document_id,
            "source_id": res.source_id,
            "status": res.status,
            "duplicate_of": res.duplicate_of,
            "chunk_count": res.chunk_count,
            "model": res.model,
            "searchable": res.searchable,
            "evidence_count": res.evidence_count,
            "sources": res.sources,
            "summary": res.summary,
        }


def main() -> None:
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
