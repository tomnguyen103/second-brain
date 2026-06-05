"""MCP server smoke test (ADR-0010): imports and registers the expected tools. DB-free."""
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from app import mcp_server
from app.config import Settings
from app.mcp_server import create_task, mcp, research_topic

_EXPECTED = {"search_notes", "create_task", "list_tasks", "send_digest", "research_topic"}


def test_registers_expected_tools():
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert _EXPECTED <= names


def test_every_tool_has_a_description():
    tools = asyncio.run(mcp.list_tools())
    for t in tools:
        assert t.description, f"tool {t.name} has no description"


def test_mcp_mutations_are_disabled_by_default(monkeypatch):
    monkeypatch.setattr(mcp_server, "settings", Settings(_env_file=None))

    with pytest.raises(PermissionError, match="MCP mutation tools are disabled"):
        create_task("write tests")
    with pytest.raises(PermissionError, match="MCP mutation tools are disabled"):
        research_topic("security review")


def test_mcp_mutations_can_be_enabled_for_trusted_clients(monkeypatch):
    class DummyTask:
        id = 7
        title = "write tests"
        detail = None
        status = "open"
        created_at = datetime.now(timezone.utc)

    @contextmanager
    def fake_session():
        yield object()

    monkeypatch.setattr(mcp_server, "settings", Settings(_env_file=None, mcp_enable_mutations=True))
    monkeypatch.setattr(mcp_server, "_session", fake_session)
    monkeypatch.setattr(mcp_server, "_create_task", lambda db, title, detail: DummyTask())

    assert create_task("write tests")["id"] == 7
