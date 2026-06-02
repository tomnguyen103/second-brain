"""MCP server smoke test (ADR-0010): imports and registers the expected tools. DB-free."""
import asyncio

from app.mcp_server import mcp

_EXPECTED = {"search_notes", "create_task", "list_tasks", "send_digest", "research_topic"}


def test_registers_expected_tools():
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert _EXPECTED <= names


def test_every_tool_has_a_description():
    tools = asyncio.run(mcp.list_tools())
    for t in tools:
        assert t.description, f"tool {t.name} has no description"
