"""briefings table — stores morning briefings for store-and-display (Phase 5, ADR-0013)

Hand-written to match the 0001-0003 style (GENERATED ALWAYS AS IDENTITY). One row per
produced briefing: the LLM summary + composed markdown over documents ingested in
(period_start, period_end]. `model` is NULL for a "nothing new" briefing (no LLM call).

Revision ID: 0004_briefings
Revises: 0003_rls_audit
Create Date: 2026-06-02
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0004_briefings"
down_revision: Union[str, None] = "0003_rls_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE briefings (
            id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            generated_at   timestamptz NOT NULL DEFAULT now(),
            period_start   timestamptz NOT NULL,
            period_end     timestamptz NOT NULL,
            summary        text NOT NULL,
            body_markdown  text NOT NULL,
            document_count integer NOT NULL DEFAULT 0,
            model          text
        )
        """
    )
    op.execute("CREATE INDEX ix_briefings_generated_at ON briefings (generated_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS briefings")
