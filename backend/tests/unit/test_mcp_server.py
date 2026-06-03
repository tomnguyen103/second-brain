"""MCP server smoke test (ADR-0010): imports and registers the expected tools. DB-free."""
import asyncio

import pytest

from app import mcp_server
from app.mcp_server import approve_pending_action, create_task, mcp
from app.vault import approvals

_EXPECTED = {
    "search_notes",
    "create_task",
    "list_tasks",
    "send_digest",
    "research_topic",
    "list_pending_approvals",
    "approve_pending_action",
}


def test_registers_expected_tools():
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert _EXPECTED <= names


def test_every_tool_has_a_description():
    tools = asyncio.run(mcp.list_tools())
    for t in tools:
        assert t.description, f"tool {t.name} has no description"


def test_write_tool_requires_approval_without_db(monkeypatch):
    monkeypatch.setattr(mcp_server.settings, "mcp_write_requires_approval", True)
    approvals._PENDING.clear()
    try:
        res = create_task("Review vault note", "safe detail")
        assert res["approval_required"] is True
        assert res["approval"]["tool"] == "create_task"
        assert res["approval"]["approved"] is False
    finally:
        approvals._PENDING.clear()


def test_approval_requires_configured_token(monkeypatch):
    monkeypatch.setattr(mcp_server.settings, "mcp_write_requires_approval", True)
    approvals._PENDING.clear()
    try:
        res = create_task("Review vault note", "safe detail")
        approval_id = res["approval"]["id"]
        with pytest.raises(approvals.ApprovalError):
            approve_pending_action(approval_id, "anything")

        monkeypatch.setattr(mcp_server.settings, "mcp_write_approval_token", "ok")
        approved = approve_pending_action(approval_id, "ok")
        assert approved["approved"] is True
        assert approved["approval"]["approved"] is True
        assert mcp_server.list_pending_approvals() == []
    finally:
        approvals._PENDING.clear()
        monkeypatch.setattr(mcp_server.settings, "mcp_write_approval_token", None)
