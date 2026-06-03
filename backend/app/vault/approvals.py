"""In-memory approval queue for local MCP vault actions.

This is intentionally process-local for v1. It prevents MCP tools from mutating the vault until
the user explicitly approves the pending call in the same local MCP session.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class PendingApproval:
    id: str
    tool: str
    args: dict
    effect: str
    summary: dict
    created_at: str


_PENDING: dict[str, PendingApproval] = {}


def _public_approval(approval: PendingApproval) -> dict:
    return {
        "id": approval.id,
        "tool": approval.tool,
        "effect": approval.effect,
        "summary": approval.summary,
        "created_at": approval.created_at,
    }


def request_approval(tool: str, args: dict, effect: str, summary: dict | None = None) -> dict:
    approval = PendingApproval(
        id=uuid4().hex,
        tool=tool,
        args=args,
        effect=effect,
        summary=summary or {},
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _PENDING[approval.id] = approval
    return {"status": "approval_required", "approval": _public_approval(approval)}


def pop_approval(approval_id: str) -> PendingApproval:
    try:
        return _PENDING.pop(approval_id)
    except KeyError as exc:
        raise ValueError("approval not found or already used") from exc


def list_pending() -> list[dict]:
    return [_public_approval(item) for item in _PENDING.values()]
