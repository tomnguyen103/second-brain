"""Enable Row-Level Security with permissive policies on user-data tables (Phase 6, ADR-0012).

RLS here is a governance capability + migration-discipline demonstration. The app connects as
the table OWNER (which bypasses RLS), and the permissive `USING (true)` policy covers any
non-owner role (e.g. a future least-privilege app role behind PgBouncer). We deliberately do
NOT `FORCE ROW LEVEL SECURITY`, so owner access is unaffected and the existing suite stays
green. The policy predicate is the documented seam for real per-tenant scoping should the app
ever become multi-user.

Revision ID: 0003_rls_audit
Revises: 0002_tasks
Create Date: 2026-06-02
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0003_rls_audit"
down_revision: Union[str, None] = "0002_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# User-data tables that carry (or reference) ingested/conversational content.
_TABLES = (
    "sources",
    "documents",
    "chunks",
    "embeddings",
    "conversations",
    "messages",
    "retrievals",
    "feedback",
)


def upgrade() -> None:
    """Enable RLS and add a permissive app-access policy on each user-data table."""
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # FOR ALL, permissive: USING governs read/update/delete visibility, WITH CHECK governs
        # insert/update. true today = "all rows"; tighten this predicate for multi-tenant later.
        op.execute(
            f"CREATE POLICY {table}_app_access ON {table} "
            f"USING (true) WITH CHECK (true)"
        )


def downgrade() -> None:
    """Drop the app-access policies and disable RLS on each user-data table."""
    for table in _TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_app_access ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
