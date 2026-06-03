"""MCP server smoke test (ADR-0010): imports and registers the expected tools. DB-free."""
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.vault import approvals
from app import mcp_server

_EXPECTED = {
    "search_notes",
    "create_task",
    "list_tasks",
    "send_digest",
    "research_topic",
    "search_vault",
    "read_note",
    "propose_note_write",
    "create_research_note",
    "capture_notebooklm_session",
    "reindex_vault",
    "vault_status",
    "pending_approvals",
    "approve_tool_call",
}


def test_registers_expected_tools():
    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {t.name for t in tools}
    assert _EXPECTED <= names


def test_every_tool_has_a_description():
    tools = asyncio.run(mcp_server.mcp.list_tools())
    for t in tools:
        assert t.description, f"tool {t.name} has no description"


@pytest.fixture(autouse=True)
def clear_pending_approvals():
    approvals._PENDING.clear()
    yield
    approvals._PENDING.clear()


@contextmanager
def _dummy_session():
    yield object()


def test_vault_action_tools_return_approval_requests():
    requests = [
        mcp_server.search_vault("agent security", top_k=500),
        mcp_server.read_note("10 Research/a.md"),
        mcp_server.propose_note_write("00 Inbox/a.md", "# A\n\nSECRET_VALUE"),
        mcp_server.create_research_note("Agent Security", "Body", sources=["paper.pdf"]),
        mcp_server.capture_notebooklm_session("NotebookLM Session", "Body", sources=["paper.pdf"]),
        mcp_server.reindex_vault(paths=["10 Research/a.md"]),
    ]

    assert len(mcp_server.pending_approvals()) == len(requests)
    for request in requests:
        assert request["status"] == "approval_required"
        approval = request["approval"]
        assert {"id", "tool", "effect", "summary", "created_at"} <= set(approval)
        assert "args" not in approval

    assert requests[0]["approval"]["summary"]["top_k"] == 50
    assert "SECRET_VALUE" not in str(requests)
    assert "SECRET_VALUE" not in str(mcp_server.pending_approvals())


def test_vault_status_reports_path_index_and_pending_counts(tmp_path, monkeypatch):
    for folder in ["10 Research", "Templates"]:
        (tmp_path / folder).mkdir()
    (tmp_path / "10 Research" / "keeper.md").write_text("# Keeper", encoding="utf-8")
    (tmp_path / "Templates" / "template.md").write_text("# Template", encoding="utf-8")
    monkeypatch.setattr(mcp_server.settings, "vault_path", str(tmp_path))
    monkeypatch.setattr(
        mcp_server, "_vault_source", lambda db: SimpleNamespace(id=42, uri=str(tmp_path))
    )

    class DummyDB:
        def scalar(self, statement):
            return 7

    @contextmanager
    def dummy_session():
        yield DummyDB()

    monkeypatch.setattr(mcp_server, "_session", dummy_session)
    mcp_server.read_note("10 Research/keeper.md")

    status = mcp_server.vault_status()

    assert status["vault_path"] == str(tmp_path.resolve())
    assert status["vault_exists"] is True
    assert status["indexed_source_exists"] is True
    assert status["indexed_source_id"] == 42
    assert status["indexed_source_uri"] == str(tmp_path)
    assert status["indexed_document_count"] == 7
    assert status["pending_approvals_count"] == 1
    assert status["markdown_files"] == {"total": 2, "eligible": 1, "excluded": 1}
    assert status["index_config"]["exclude_dirs"] == [".obsidian", "Templates", "90 Archive"]


def test_legacy_mutating_tools_return_approval_requests_and_hide_raw_details():
    requests = [
        mcp_server.create_task("Keeper review", "SECRET_TASK_DETAIL"),
        mcp_server.research_topic("Approval-gated durable memory"),
    ]

    assert len(mcp_server.pending_approvals()) == len(requests)
    assert [request["approval"]["tool"] for request in requests] == [
        "create_task",
        "research_topic",
    ]
    for request in requests:
        assert request["status"] == "approval_required"
        assert "args" not in request["approval"]

    assert "SECRET_TASK_DETAIL" not in str(requests)
    assert "SECRET_TASK_DETAIL" not in str(mcp_server.pending_approvals())


def test_rejected_legacy_mutating_tools_do_not_call_services(monkeypatch):
    calls = []
    monkeypatch.setattr(mcp_server, "_create_task", lambda *args, **kwargs: calls.append("task"))
    monkeypatch.setattr(
        mcp_server, "_research_topic", lambda *args, **kwargs: calls.append("research")
    )

    task = mcp_server.create_task("Rejected task", "no write")
    research = mcp_server.research_topic("Rejected research")

    assert mcp_server.approve_tool_call(task["approval"]["id"], decision="reject")[
        "status"
    ] == "rejected"
    assert mcp_server.approve_tool_call(research["approval"]["id"], decision="reject")[
        "status"
    ] == "rejected"
    assert calls == []


def test_approved_legacy_create_task_requires_token_and_mutates_once(monkeypatch):
    calls = []
    monkeypatch.setattr(mcp_server.settings, "mcp_approval_token", "local-human-ok")
    monkeypatch.setattr(mcp_server, "_session", _dummy_session)

    def fake_create_task(db, title, detail):
        calls.append((title, detail))
        return SimpleNamespace(
            id=123,
            title=title,
            detail=detail,
            status="open",
            created_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
        )

    monkeypatch.setattr(mcp_server, "_create_task", fake_create_task)

    request = mcp_server.create_task("Token task", "approved detail")
    approval_id = request["approval"]["id"]

    missing = mcp_server.approve_tool_call(approval_id)
    wrong = mcp_server.approve_tool_call(approval_id, approval_token="wrong")

    assert missing["status"] == "approval_token_required"
    assert wrong["status"] == "approval_token_required"
    assert len(mcp_server.pending_approvals()) == 1
    assert calls == []

    approved = mcp_server.approve_tool_call(
        approval_id, approval_token="local-human-ok"
    )

    assert approved["status"] == "approved"
    assert approved["tool"] == "create_task"
    assert approved["task"]["id"] == 123
    assert calls == [("Token task", "approved detail")]


def test_approved_legacy_research_topic_runs_only_after_approval(monkeypatch):
    calls = []
    embedder = object()
    llm = object()
    monkeypatch.setattr(mcp_server, "_session", _dummy_session)
    monkeypatch.setattr(mcp_server, "get_embedder", lambda: embedder)
    monkeypatch.setattr(mcp_server, "get_llm_client", lambda settings: llm)

    def fake_research_topic(db, used_embedder, used_llm, topic):
        calls.append((used_embedder, used_llm, topic))
        return SimpleNamespace(
            topic=topic,
            document_id=7,
            source_id=8,
            status="embedded",
            duplicate_of=None,
            chunk_count=1,
            model="fake",
            searchable=True,
            summary="approved summary",
        )

    monkeypatch.setattr(mcp_server, "_research_topic", fake_research_topic)

    request = mcp_server.research_topic("Legacy research")
    assert calls == []

    approved = mcp_server.approve_tool_call(request["approval"]["id"])

    assert approved["status"] == "approved"
    assert approved["tool"] == "research_topic"
    assert approved["research"]["document_id"] == 7
    assert calls == [(embedder, llm, "Legacy research")]


def test_approved_reindex_vault_reports_clear_counts(monkeypatch):
    embedder = object()
    calls = []
    monkeypatch.setattr(mcp_server, "_session", _dummy_session)
    monkeypatch.setattr(mcp_server, "get_embedder", lambda: embedder)

    def fake_index_vault(db, used_embedder, used_settings, *, paths=None):
        calls.append((used_embedder, used_settings, paths))
        return SimpleNamespace(
            source_id=9,
            requested=3,
            indexed=2,
            skipped=1,
            removed_stale=4,
            excluded=5,
        )

    monkeypatch.setattr(mcp_server, "index_vault", fake_index_vault)

    request = mcp_server.reindex_vault(paths=["10 Research/a.md"])
    approved = mcp_server.approve_tool_call(request["approval"]["id"])

    assert approved["status"] == "approved"
    assert approved["tool"] == "reindex_vault"
    assert approved["result"] == {
        "source_id": 9,
        "requested": 3,
        "indexed": 2,
        "skipped": 1,
        "removed_stale": 4,
        "excluded": 5,
    }
    assert calls == [(embedder, mcp_server.settings, ["10 Research/a.md"])]


def test_approve_tool_call_writes_then_reads_vault_note(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server.settings, "vault_path", str(tmp_path))

    request = mcp_server.propose_note_write(
        "00 Inbox/test-note.md",
        "# Test Note\n\nApproval-gated local memory.",
    )
    write_result = mcp_server.approve_tool_call(request["approval"]["id"])

    assert write_result["status"] == "approved"
    assert write_result["note"]["path"] == "00 Inbox/test-note.md"
    assert "content" not in write_result["note"]

    read_request = mcp_server.read_note("00 Inbox/test-note.md")
    read_result = mcp_server.approve_tool_call(read_request["approval"]["id"])

    assert read_result["status"] == "approved"
    assert read_result["note"]["title"] == "Test Note"
    assert "Approval-gated local memory." in read_result["note"]["content"]
    assert read_result["note"]["truncated"] is False


def test_rejected_tool_call_does_not_write_note(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server.settings, "vault_path", str(tmp_path))

    request = mcp_server.propose_note_write("00 Inbox/rejected.md", "# Rejected")
    result = mcp_server.approve_tool_call(request["approval"]["id"], decision="reject")

    assert result["status"] == "rejected"
    assert not (tmp_path / "00 Inbox" / "rejected.md").exists()


def test_invalid_approval_decision_keeps_pending_note(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server.settings, "vault_path", str(tmp_path))

    request = mcp_server.propose_note_write("00 Inbox/typo.md", "# Typo")
    approval_id = request["approval"]["id"]
    result = mcp_server.approve_tool_call(approval_id, decision="aprove")

    assert result["status"] == "invalid_decision"
    assert len(mcp_server.pending_approvals()) == 1
    assert not (tmp_path / "00 Inbox" / "typo.md").exists()

    approved = mcp_server.approve_tool_call(approval_id, decision="yes")
    assert approved["status"] == "approved"
    assert (tmp_path / "00 Inbox" / "typo.md").exists()


def test_approve_tool_call_requires_token_when_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server.settings, "vault_path", str(tmp_path))
    monkeypatch.setattr(mcp_server.settings, "mcp_approval_token", "local-human-ok")

    request = mcp_server.propose_note_write("00 Inbox/token.md", "# Token")
    approval_id = request["approval"]["id"]

    missing = mcp_server.approve_tool_call(approval_id)
    wrong = mcp_server.approve_tool_call(approval_id, approval_token="nope")

    assert missing["status"] == "approval_token_required"
    assert wrong["status"] == "approval_token_required"
    assert len(mcp_server.pending_approvals()) == 1
    assert not (tmp_path / "00 Inbox" / "token.md").exists()

    approved = mcp_server.approve_tool_call(
        approval_id, approval_token="local-human-ok"
    )

    assert approved["status"] == "approved"
    assert (tmp_path / "00 Inbox" / "token.md").exists()


def test_reject_tool_call_requires_token_when_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server.settings, "vault_path", str(tmp_path))
    monkeypatch.setattr(mcp_server.settings, "mcp_approval_token", "local-human-ok")

    request = mcp_server.propose_note_write("00 Inbox/reject-token.md", "# Token")
    approval_id = request["approval"]["id"]

    blocked = mcp_server.approve_tool_call(
        approval_id, decision="reject", approval_token="wrong"
    )
    rejected = mcp_server.approve_tool_call(
        approval_id, decision="reject", approval_token="local-human-ok"
    )

    assert blocked["status"] == "approval_token_required"
    assert rejected["status"] == "rejected"
    assert not (tmp_path / "00 Inbox" / "reject-token.md").exists()


def test_rejected_generated_note_calls_do_not_write_files(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server.settings, "vault_path", str(tmp_path))

    research = mcp_server.create_research_note("Rejected Research", "Body")
    capture = mcp_server.capture_notebooklm_session("Rejected Capture", "Body")

    assert mcp_server.approve_tool_call(research["approval"]["id"], decision="reject")[
        "status"
    ] == "rejected"
    assert mcp_server.approve_tool_call(capture["approval"]["id"], decision="reject")[
        "status"
    ] == "rejected"
    assert not list(tmp_path.rglob("*.md"))


def test_approve_generated_note_uses_template_and_concise_output(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server.settings, "vault_path", str(tmp_path))

    request = mcp_server.create_research_note(
        "Agent Security",
        "Keep durable memory local.",
        sources=["manual NotebookLM synthesis"],
    )
    result = mcp_server.approve_tool_call(request["approval"]["id"])

    assert result["status"] == "approved"
    assert result["note"]["path"] == "10 Research/Agent-Security.md"
    assert result["note"]["title"] == "Agent Security"
    assert "content" not in result["note"]
    saved = (tmp_path / "10 Research" / "Agent-Security.md").read_text(encoding="utf-8")
    assert "## Synthesis" in saved
    assert "- manual NotebookLM synthesis" in saved


def test_propose_note_write_rejects_invalid_mode_before_queueing():
    with pytest.raises(ValueError):
        mcp_server.propose_note_write("00 Inbox/a.md", "# A", mode="delete")
    assert mcp_server.pending_approvals() == []
