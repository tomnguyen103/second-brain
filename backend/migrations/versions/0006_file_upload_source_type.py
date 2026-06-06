"""allow generic file upload sources

Revision ID: 0006_file_upload_source_type
Revises: 0005_eval_cases
Create Date: 2026-06-05
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0006_file_upload_source_type"
down_revision: Union[str, None] = "0005_eval_cases"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TYPES = (
    "'notes_folder','github','rss','pdf_upload','file_upload',"
    "'bookmark','research_note','manual'"
)
_OLD_TYPES = "'notes_folder','github','rss','pdf_upload','bookmark','research_note','manual'"


def upgrade() -> None:
    op.execute("ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_type_check")
    op.execute("ALTER TABLE sources DROP CONSTRAINT IF EXISTS ck_sources_type")
    op.execute(f"ALTER TABLE sources ADD CONSTRAINT ck_sources_type CHECK (type IN ({_NEW_TYPES}))")


def downgrade() -> None:
    op.execute("UPDATE sources SET type = 'manual' WHERE type = 'file_upload'")
    op.execute("ALTER TABLE sources DROP CONSTRAINT IF EXISTS ck_sources_type")
    op.execute(f"ALTER TABLE sources ADD CONSTRAINT ck_sources_type CHECK (type IN ({_OLD_TYPES}))")
