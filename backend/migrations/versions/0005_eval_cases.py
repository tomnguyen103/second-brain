"""durable reviewed eval cases

Store feedback-promoted eval cases in Postgres instead of mutating the source-controlled
dataset file from the production API container.

Revision ID: 0005_eval_cases
Revises: 0004_briefings
Create Date: 2026-06-05
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005_eval_cases"
down_revision: Union[str, None] = "0004_briefings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE eval_cases (
            id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            case_id           text NOT NULL,
            feedback_id       bigint REFERENCES feedback(id) ON DELETE SET NULL,
            question          text NOT NULL,
            expected_docs     jsonb NOT NULL DEFAULT '[]'::jsonb,
            expected_keywords jsonb NOT NULL DEFAULT '[]'::jsonb,
            expect_refusal    boolean NOT NULL DEFAULT false,
            review            jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at        timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_eval_cases_case_id UNIQUE (case_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_eval_cases_feedback_id ON eval_cases (feedback_id)")
    op.execute("ALTER TABLE eval_cases ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY eval_cases_app_access ON eval_cases "
        "USING (true) WITH CHECK (true)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS eval_cases_app_access ON eval_cases")
    op.execute("DROP TABLE IF EXISTS eval_cases")
