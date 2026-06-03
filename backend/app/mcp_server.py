"""MCP server — exposes Second Brain's agentic actions as tools (Phase 4, ADR-0010).

Thin layer over the tested services: each tool opens its own DB session, builds the embedder/LLM,
calls a service, and returns a JSON-able result. Run it over stdio:

    python -m app.mcp_server

then point an MCP client (Claude Desktop config, or `mcp dev`/Inspector) at that command. The LLM
provider follows config (Gemini default; set SECOND_BRAIN_LLM_PROVIDER=fake for a keyless smoke).

Local-first vault tools are the preferred private-memory surface. Legacy DB mutating tools are
kept for demo/backward compatibility, but they now share the same approval queue as vault writes.
"""
from __future__ import annotations

from contextlib import contextmanager
from hmac import compare_digest

from mcp.server.fastmcp import FastMCP
from sqlalchemy import func, select

from app.config import settings
from app.db.models import Document, Source
from app.db.session import SessionLocal
from app.deps import get_embedder
from app.digest.service import build_digest
from app.ingest.hashing import content_hash
from app.llm.factory import get_llm_client
from app.research.service import research_topic as _research_topic
from app.retrieval.hybrid import hybrid_search, load_display_chunks
from app.tasks.service import create_task as _create_task
from app.tasks.service import list_tasks as _list_tasks
from app.vault import approvals
from app.vault.indexer import VAULT_SOURCE_NAME, index_vault
from app.vault.paths import vault_root
from app.vault.service import (
    capture_notebooklm_session as _capture_notebooklm_session,
)
from app.vault.service import create_research_note as _create_vault_research_note
from app.vault.service import list_markdown_files
from app.vault.service import read_note as _read_vault_note
from app.vault.service import write_note as _write_vault_note

mcp = FastMCP("second-brain")

_NOTE_CONTENT_LIMIT = 8000
_TEXT_PREVIEW_LIMIT = 240


@contextmanager
def _session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _format_search_hits(db, hits, *, include_vault_path: bool = False) -> list[dict]:
    display = load_display_chunks(db, [h.chunk_id for h in hits])
    vault_paths: dict[int, str | None] = {}
    if include_vault_path and display:
        document_ids = [dc.document_id for dc in display.values()]
        rows = db.execute(
            select(Document.id, Document.external_id).where(Document.id.in_(document_ids))
        ).all()
        vault_paths = {int(row.id): row.external_id for row in rows}

    out = []
    for h in hits:
        dc = display.get(h.chunk_id)
        if dc is None:
            continue
        item = {
            "document_id": dc.document_id,
            "document_title": dc.document_title,
            "source_name": dc.source_name,
            "snippet": (dc.content or "")[:300],
            "score": h.score,
            "method": h.method,
        }
        if include_vault_path:
            item["vault_path"] = vault_paths.get(dc.document_id)
        out.append(item)
    return out


def _vault_source(db) -> Source | None:
    return db.scalar(
        select(Source).where(Source.type == "notes_folder", Source.name == VAULT_SOURCE_NAME)
    )


def _preview(text: str, limit: int = _TEXT_PREVIEW_LIMIT) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _content_stats(text: str) -> dict:
    return {"chars": len(text or ""), "hash": content_hash(text or "")}


def _note_payload(note, *, include_content: bool = False) -> dict:
    payload = {
        "path": note.path,
        "title": note.title,
        "tags": note.tags,
        "frontmatter": note.metadata,
        "content_hash": note.content_hash,
        "mtime": note.mtime,
    }
    if include_content:
        content = note.content
        payload["content"] = content[:_NOTE_CONTENT_LIMIT]
        payload["content_chars"] = len(content)
        payload["truncated"] = len(content) > _NOTE_CONTENT_LIMIT
    return payload


def _write_summary(path: str, content: str, mode: str) -> dict:
    return {"path": path, "mode": mode, "content": _content_stats(content)}


def _generated_note_summary(*, title: str, body: str, folder: str, sources: list[str]) -> dict:
    return {
        "title": _preview(title),
        "folder": folder,
        "body": _content_stats(body),
        "sources_count": len(sources),
        "sources_preview": [_preview(source, 80) for source in sources[:5]],
    }


def _task_summary(title: str, detail: str) -> dict:
    return {
        "title": _preview(title),
        "detail": _content_stats(detail) if detail else {"chars": 0, "hash": None},
    }


def _task_payload(task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "detail": task.detail,
        "status": task.status,
        "created_at": task.created_at.isoformat(),
    }


def _legacy_research_payload(result) -> dict:
    return {
        "topic": result.topic,
        "document_id": result.document_id,
        "source_id": result.source_id,
        "status": result.status,
        "duplicate_of": result.duplicate_of,
        "chunk_count": result.chunk_count,
        "model": result.model,
        "searchable": result.searchable,
        "summary": result.summary,
    }


def _approval_token_valid(approval_token: str) -> bool:
    expected = settings.mcp_approval_token
    if not expected:
        return True
    return compare_digest(approval_token or "", expected)


@mcp.tool()
def search_notes(query: str, top_k: int = 5) -> list[dict]:
    """Legacy/demo DB read-only search across indexed notes; prefer search_vault for private memory."""
    top_k = max(1, min(top_k, 50))   # clamp client-controlled top_k (SQL LIMIT)
    with _session() as db:
        hits, _meta = hybrid_search(db, get_embedder(), settings, query, top_k=top_k)
        return _format_search_hits(db, hits)


@mcp.tool()
def create_task(title: str, detail: str = "") -> dict:
    """Request approval to add a task to the legacy/demo DB task list."""
    title = (title or "").strip()
    if not title:
        raise ValueError("task title is required")
    detail = detail or ""
    return approvals.request_approval(
        "create_task",
        {"title": title, "detail": detail},
        f"Legacy DB write: create task {_preview(title)!r}.",
        _task_summary(title, detail),
    )


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
    """Legacy/demo DB read-only digest of recent activity; this composes markdown only."""
    limit = max(1, min(limit, 100))   # clamp client-controlled limit (SQL LIMIT)
    with _session() as db:
        return build_digest(db, limit=limit)


@mcp.tool()
def research_topic(topic: str) -> dict:
    """Request approval to generate and store a legacy/demo DB research note."""
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("research topic is required")
    return approvals.request_approval(
        "research_topic",
        {"topic": topic},
        f"Legacy DB write: generate and index research note for {_preview(topic)!r}.",
        {"topic": _preview(topic)},
    )


@mcp.tool()
def search_vault(query: str, top_k: int = 5) -> dict:
    """Request approval to search the local Obsidian vault-derived index."""
    top_k = max(1, min(top_k, 50))
    return approvals.request_approval(
        "search_vault",
        {"query": query, "top_k": top_k},
        "Search the local Obsidian vault-derived index.",
        {"query": _preview(query), "top_k": top_k},
    )


@mcp.tool()
def read_note(path: str) -> dict:
    """Request approval to read one Markdown note from the configured Obsidian vault."""
    return approvals.request_approval(
        "read_note",
        {"path": path},
        f"Read vault note: {path}",
        {"path": path},
    )


@mcp.tool()
def propose_note_write(path: str, content: str, mode: str = "create") -> dict:
    """Request approval to create, append, or overwrite a Markdown note in the vault."""
    mode = (mode or "create").lower()
    if mode not in {"create", "append", "overwrite"}:
        raise ValueError("mode must be create, append, or overwrite")
    return approvals.request_approval(
        "propose_note_write",
        {"path": path, "content": content, "mode": mode},
        f"Write Markdown note in {mode!r} mode: {path}",
        _write_summary(path, content, mode),
    )


@mcp.tool()
def create_research_note(topic: str, body: str, sources: list[str] | None = None) -> dict:
    """Request approval to save a curated research note to the Obsidian vault."""
    sources = sources or []
    return approvals.request_approval(
        "create_research_note",
        {"topic": topic, "body": body, "sources": sources},
        f"Create research note in the Obsidian vault: {topic}",
        _generated_note_summary(title=topic, body=body, folder="10 Research", sources=sources),
    )


@mcp.tool()
def capture_notebooklm_session(title: str, body: str, sources: list[str] | None = None) -> dict:
    """Request approval to save a NotebookLM-derived session note to the Obsidian vault."""
    sources = sources or []
    return approvals.request_approval(
        "capture_notebooklm_session",
        {"title": title, "body": body, "sources": sources},
        f"Create NotebookLM capture note in the Obsidian vault: {title}",
        _generated_note_summary(
            title=title, body=body, folder="50 Agent Outputs", sources=sources
        ),
    )


@mcp.tool()
def reindex_vault(paths: list[str] | None = None) -> dict:
    """Request approval to index all or selected Obsidian Markdown files into local Postgres."""
    paths = paths or None
    return approvals.request_approval(
        "reindex_vault",
        {"paths": paths},
        "Rebuild the local derived search index for the Obsidian vault.",
        {
            "scope": "selected" if paths else "all",
            "paths_count": len(paths) if paths else None,
            "paths_preview": paths[:10] if paths else [],
            "include_dirs": settings.vault_index_include_dirs,
            "exclude_dirs": settings.vault_index_exclude_dirs,
        },
    )


@mcp.tool()
def vault_status() -> dict:
    """Report the local Obsidian vault path, derived index state, and pending approvals."""
    root = vault_root(settings.vault_path)
    vault_exists = root.exists() and root.is_dir()
    total_markdown = len(list_markdown_files(settings.vault_path)) if vault_exists else 0
    eligible_markdown = (
        len(
            list_markdown_files(
                settings.vault_path,
                include_dirs=settings.vault_index_include_dirs,
                exclude_dirs=settings.vault_index_exclude_dirs,
            )
        )
        if vault_exists
        else 0
    )
    with _session() as db:
        source = _vault_source(db)
        indexed_count = 0
        if source is not None:
            indexed_count = db.scalar(
                select(func.count()).select_from(Document).where(Document.source_id == source.id)
            ) or 0
        return {
            "vault_path": str(root),
            "vault_exists": vault_exists,
            "indexed_source_exists": source is not None,
            "indexed_source_id": source.id if source is not None else None,
            "indexed_source_uri": getattr(source, "uri", None) if source is not None else None,
            "indexed_document_count": int(indexed_count),
            "pending_approvals_count": len(approvals.list_pending()),
            "markdown_files": {
                "total": total_markdown,
                "eligible": eligible_markdown,
                "excluded": max(0, total_markdown - eligible_markdown),
            },
            "index_config": {
                "include_dirs": settings.vault_index_include_dirs,
                "exclude_dirs": settings.vault_index_exclude_dirs,
            },
        }


@mcp.tool()
def pending_approvals() -> list[dict]:
    """List approval-gated local MCP actions waiting in this server process."""
    return approvals.list_pending()


@mcp.tool()
def approve_tool_call(approval_id: str, decision: str = "approve",
                      approval_token: str = "") -> dict:
    """Approve or reject one pending local MCP tool call."""
    if not _approval_token_valid(approval_token):
        return {
            "status": "approval_token_required",
            "approval_id": approval_id,
            "message": "approval token missing or invalid; pending action was not consumed",
        }

    normalized_decision = (decision or "").strip().lower()
    approve_decisions = {"approve", "approved", "yes"}
    reject_decisions = {"reject", "rejected", "no"}
    if normalized_decision not in approve_decisions | reject_decisions:
        return {
            "status": "invalid_decision",
            "approval_id": approval_id,
            "message": "decision must be approve/approved/yes or reject/rejected/no",
        }

    approval = approvals.pop_approval(approval_id)
    if normalized_decision in reject_decisions:
        return {"status": "rejected", "approval_id": approval_id, "tool": approval.tool}

    args = approval.args
    if approval.tool == "create_task":
        with _session() as db:
            task = _create_task(db, args["title"], args.get("detail") or None)
            return {"status": "approved", "tool": approval.tool, "task": _task_payload(task)}

    if approval.tool == "research_topic":
        with _session() as db:
            result = _research_topic(db, get_embedder(), get_llm_client(settings), args["topic"])
            return {
                "status": "approved",
                "tool": approval.tool,
                "research": _legacy_research_payload(result),
            }

    if approval.tool == "read_note":
        note = _read_vault_note(settings.vault_path, args["path"])
        return {"status": "approved", "tool": approval.tool, "note": _note_payload(note, include_content=True)}

    if approval.tool == "propose_note_write":
        note = _write_vault_note(
            settings.vault_path, args["path"], args["content"], mode=args.get("mode", "create")
        )
        return {"status": "approved", "tool": approval.tool, "note": _note_payload(note)}

    if approval.tool == "create_research_note":
        note = _create_vault_research_note(
            settings.vault_path,
            topic=args["topic"],
            body=args["body"],
            sources=args.get("sources") or [],
        )
        return {"status": "approved", "tool": approval.tool, "note": _note_payload(note)}

    if approval.tool == "capture_notebooklm_session":
        note = _capture_notebooklm_session(
            settings.vault_path,
            title=args["title"],
            body=args["body"],
            sources=args.get("sources") or [],
        )
        return {"status": "approved", "tool": approval.tool, "note": _note_payload(note)}

    if approval.tool == "reindex_vault":
        with _session() as db:
            result = index_vault(db, get_embedder(), settings, paths=args.get("paths"))
            return {"status": "approved", "tool": approval.tool, "result": result.__dict__}

    if approval.tool == "search_vault":
        with _session() as db:
            source = _vault_source(db)
            if source is None:
                return {"status": "approved", "tool": approval.tool, "query": args["query"], "hits": []}
            hits, meta = hybrid_search(
                db,
                get_embedder(),
                settings,
                args["query"],
                top_k=args.get("top_k", 5),
                source_ids=[source.id],
            )
            return {"status": "approved", "tool": approval.tool, "query": args["query"],
                    "hits": _format_search_hits(db, hits, include_vault_path=True),
                    "retrieval": meta}

    raise ValueError(f"unknown approval tool: {approval.tool}")


def main() -> None:
    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
