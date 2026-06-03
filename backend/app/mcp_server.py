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
from app.security import ensure_no_sensitive_content, redact_sensitive_text
from app.tasks.service import create_task as _create_task
from app.tasks.service import list_tasks as _list_tasks
from app.vault import approvals

mcp = FastMCP("second-brain")


@contextmanager
def _session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _approval_required(tool: str, args: dict, *, effect: str, summary: str,
                       approval_id: str | None) -> dict | None:
    if not settings.mcp_write_requires_approval:
        return None
    if not approval_id:
        return approvals.request_approval(tool, args, effect=effect, summary=summary)
    approvals.pop_approved(approval_id, tool=tool, args=args)
    return None


def _llm_label() -> str:
    if settings.llm_provider == "gemini":
        return f"gemini/{settings.gemini_model}"
    if settings.llm_provider == "ollama":
        return f"ollama/{settings.ollama_model}"
    return settings.llm_provider


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
                "document_title": redact_sensitive_text(dc.document_title),
                "source_name": redact_sensitive_text(dc.source_name),
                "snippet": redact_sensitive_text((dc.content or "")[:300]),
                "score": h.score,
                "method": h.method,
            })
        return out


@mcp.tool()
def create_task(title: str, detail: str = "", approval_id: str = "") -> dict:
    """Add a task to the user's task list. Returns the created task."""
    ensure_no_sensitive_content(title, detail, context="MCP create_task")
    args = {"title": title, "detail": detail or ""}
    approval = _approval_required(
        "create_task",
        args,
        effect="create a durable task in the Second Brain database",
        summary=f"Create task: {title}",
        approval_id=approval_id or None,
    )
    if approval is not None:
        return approval
    with _session() as db:
        t = _create_task(db, title, detail or None)
        return {"id": t.id, "title": redact_sensitive_text(t.title),
                "detail": redact_sensitive_text(t.detail),
                "status": t.status, "created_at": t.created_at.isoformat()}


@mcp.tool()
def list_tasks(status: str = "", limit: int = 20) -> list[dict]:
    """List tasks, optionally filtered by status (open|done|cancelled)."""
    limit = max(1, min(limit, 100))   # clamp client-controlled limit (SQL LIMIT)
    with _session() as db:
        tasks = _list_tasks(db, status=status or None, limit=limit)
        return [{"id": t.id, "title": redact_sensitive_text(t.title),
                 "detail": redact_sensitive_text(t.detail),
                 "status": t.status, "created_at": t.created_at.isoformat()} for t in tasks]


@mcp.tool()
def send_digest(limit: int = 10) -> str:
    """Compose a markdown digest of recent activity (recently added documents + counts)."""
    limit = max(1, min(limit, 100))   # clamp client-controlled limit (SQL LIMIT)
    with _session() as db:
        return redact_sensitive_text(build_digest(db, limit=limit))


@mcp.tool()
def research_topic(topic: str, approval_id: str = "") -> dict:
    """Research a topic with the LLM, store it as a research note, and auto-index it so it
    becomes permanently searchable in the second brain."""
    ensure_no_sensitive_content(topic, context="MCP research_topic")
    args = {"topic": topic}
    approval = _approval_required(
        "research_topic",
        args,
        effect="call the configured LLM and store a searchable research_note in Postgres",
        summary=(
            f"Research topic via {_llm_label()}: "
            f"{redact_sensitive_text(topic)}"
        ),
        approval_id=approval_id or None,
    )
    if approval is not None:
        return approval
    with _session() as db:
        res = _research_topic(db, get_embedder(), get_llm_client(settings), topic)
        return {
            "topic": redact_sensitive_text(res.topic),
            "document_id": res.document_id,
            "source_id": res.source_id,
            "status": res.status,
            "duplicate_of": res.duplicate_of,
            "chunk_count": res.chunk_count,
            "model": res.model,
            "searchable": res.searchable,
            "summary": redact_sensitive_text(res.summary),
        }


@mcp.tool()
def list_pending_approvals() -> list[dict]:
    """List pending MCP write approvals without exposing raw secrets."""
    return approvals.list_pending()


@mcp.tool()
def approve_pending_action(approval_id: str, approval_token: str) -> dict:
    """Approve one pending MCP write action using the local approval token."""
    return approvals.approve(
        approval_id,
        approval_token=approval_token,
        expected_token=settings.mcp_write_approval_token,
    )


def main() -> None:
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
