"""Row-Level Security is enabled on user-data tables (Phase 6, ADR-0012, migration 0003).
Requires `alembic upgrade head` to have applied 0003."""
import os

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.getenv("SECOND_BRAIN_TEST_DATABASE_URL"), reason="no test DB"
)

RLS_TABLES = [
    "sources",
    "documents",
    "chunks",
    "embeddings",
    "conversations",
    "messages",
    "retrievals",
    "feedback",
]


@pytest.mark.parametrize("table", RLS_TABLES)
def test_rls_enabled(db_session, table):
    enabled = db_session.execute(
        text("SELECT relrowsecurity FROM pg_class WHERE relname = :t"), {"t": table}
    ).scalar()
    assert enabled is True, f"RLS not enabled on {table} — run alembic upgrade head"


@pytest.mark.parametrize("table", RLS_TABLES)
def test_app_access_policy_exists(db_session, table):
    count = db_session.execute(
        text("SELECT count(*) FROM pg_policies WHERE tablename = :t AND policyname = :p"),
        {"t": table, "p": f"{table}_app_access"},
    ).scalar()
    assert count == 1
