"""App-layer audit logging (ADR-0012).

Every governed data action (export, delete, retention purge) writes an `audit_log` row
through this service rather than via a DB trigger — explicit about actor/action/entity,
portable, and unit/integration-testable.

Transaction ownership: `record()` flushes but does NOT commit. The calling service or
endpoint owns the transaction, so the audit row and the action it records commit atomically
(and roll back together — which is what keeps the test `db_session` clean).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AuditLog

# Mirrors the ck_audit_action CHECK constraint on audit_log.action.
ACTIONS = ("read", "create", "update", "delete", "export")


def record(
    db: Session,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    detail: dict | None = None,
    enabled: bool = True,
) -> AuditLog | None:
    """Write one audit row. Returns the row, or None when auditing is disabled.

    `action` must be one of ACTIONS; an out-of-range value hits the DB CHECK constraint
    (ck_audit_action) and raises IntegrityError — we intentionally let the DB enforce it.
    """
    if not enabled:
        return None
    row = AuditLog(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail or {},
    )
    db.add(row)
    db.flush()
    return row
