"""tasks table — backs the MCP create_task agentic action (Phase 4)

Hand-written to match the 0001 style (GENERATED ALWAYS AS IDENTITY). A user task is distinct
from a pipeline `job` (ADR-0004) — see ADR-0010.

Revision ID: 0002_tasks
Revises: 0001_baseline
Create Date: 2026-06-02
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_tasks"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tasks (
            id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            title      text NOT NULL,
            detail     text,
            status     text NOT NULL DEFAULT 'open'
                       CHECK (status IN ('open','done','cancelled')),
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_tasks_status ON tasks (status)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tasks")
