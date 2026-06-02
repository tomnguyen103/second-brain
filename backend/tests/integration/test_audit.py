"""Audit-log service round-trip (Phase 6, ADR-0012)."""
import os

import pytest
from sqlalchemy.exc import IntegrityError

from app.dataops import audit
from app.db.models import AuditLog

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB"
)


def test_record_writes_row(db_session):
    row = audit.record(
        db_session,
        actor="tester",
        action="export",
        entity_type="source",
        entity_id=42,
        detail={"k": "v"},
    )
    assert row is not None and row.id is not None
    fetched = db_session.get(AuditLog, row.id)
    assert fetched.actor == "tester"
    assert fetched.action == "export"
    assert fetched.entity_type == "source"
    assert fetched.entity_id == 42
    assert fetched.detail == {"k": "v"}


def test_record_disabled_returns_none(db_session):
    row = audit.record(
        db_session, actor="t", action="read", entity_type="source", enabled=False
    )
    assert row is None
    assert db_session.query(AuditLog).count() == 0


def test_record_invalid_action_violates_check(db_session):
    # SAVEPOINT so the failed INSERT rolls back without aborting the outer test transaction.
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            audit.record(db_session, actor="t", action="frobnicate", entity_type="source")
