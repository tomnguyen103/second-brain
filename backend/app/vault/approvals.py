"""In-memory approval gate for MCP write tools."""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.security import redact_sensitive_value


class ApprovalError(ValueError):
    """Raised when an MCP write approval is missing, invalid, or unsafe."""


@dataclass
class PendingApproval:
    id: str
    tool: str
    args_hash: str
    public_args: dict
    effect: str
    summary: str
    created_at: str
    approved: bool = False
    approved_at: str | None = None


_PENDING: dict[str, PendingApproval] = {}
_LOCK = threading.Lock()


def _args_hash(args: dict) -> str:
    encoded = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _public_approval(approval: PendingApproval) -> dict:
    return {
        "id": approval.id,
        "tool": approval.tool,
        "args": approval.public_args,
        "effect": approval.effect,
        "summary": approval.summary,
        "created_at": approval.created_at,
        "approved": approval.approved,
        "approved_at": approval.approved_at,
    }


def request_approval(tool: str, args: dict, *, effect: str, summary: str) -> dict:
    approval = PendingApproval(
        id=uuid4().hex,
        tool=tool,
        args_hash=_args_hash(args),
        public_args=redact_sensitive_value(args),
        effect=effect,
        summary=redact_sensitive_value(summary),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    with _LOCK:
        _PENDING[approval.id] = approval
        public = _public_approval(approval)
    return {"approval_required": True, "approval": public}


def approve(approval_id: str, *, approval_token: str, expected_token: str | None) -> dict:
    if not expected_token:
        raise ApprovalError("MCP write approval token is not configured; write tools are disabled")
    if approval_token != expected_token:
        raise ApprovalError("invalid MCP write approval token")
    with _LOCK:
        approval = _PENDING.get(approval_id)
        if approval is None:
            raise ApprovalError("approval not found or already used")
        approval.approved = True
        approval.approved_at = datetime.now(timezone.utc).isoformat()
        public = _public_approval(approval)
    return {"approved": True, "approval": public}


def pop_approved(approval_id: str, *, tool: str, args: dict) -> PendingApproval:
    with _LOCK:
        approval = _PENDING.get(approval_id)
        if approval is None:
            raise ApprovalError("approval not found or already used")
        if not approval.approved:
            raise ApprovalError("approval has not been approved yet")
        if approval.tool != tool or approval.args_hash != _args_hash(args):
            raise ApprovalError("approval does not match this tool call")
        return _PENDING.pop(approval_id)


def list_pending() -> list[dict]:
    with _LOCK:
        return [_public_approval(item) for item in _PENDING.values() if not item.approved]
