"""Task service vs real DB (Phase 4, ADR-0010)."""
import os

import pytest

from app.tasks.service import create_task, list_tasks

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB")


def test_create_and_list(db_session):
    t = create_task(db_session, "Buy milk", "2 liters, oat")
    assert t.id and t.title == "Buy milk" and t.detail == "2 liters, oat" and t.status == "open"
    listed = list_tasks(db_session)
    assert any(x.id == t.id for x in listed)


def test_status_filter(db_session):
    t = create_task(db_session, "open task")
    open_only = list_tasks(db_session, status="open")
    assert any(x.id == t.id for x in open_only)
    done_only = list_tasks(db_session, status="done")
    assert all(x.status == "done" for x in done_only)
    assert t.id not in {x.id for x in done_only}


def test_empty_title_rejected(db_session):
    with pytest.raises(ValueError):
        create_task(db_session, "   ")


def test_invalid_status_filter_rejected(db_session):
    with pytest.raises(ValueError):
        list_tasks(db_session, status="bogus")
