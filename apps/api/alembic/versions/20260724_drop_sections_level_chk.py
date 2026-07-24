"""Drop document_sections_level_chk (allow H1–H6 levels).

Revision ID: 20260724_drop_sections_level_chk
Revises: 20260723_audit_cols_source_key
Create Date: 2026-07-24
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260724_drop_sections_level_chk"
down_revision: Union[str, Sequence[str], None] = "20260723_audit_cols_source_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
ALTER TABLE rag_service.document_sections
  DROP CONSTRAINT IF EXISTS document_sections_level_chk;
"""
    )


def downgrade() -> None:
    op.execute(
        """
ALTER TABLE rag_service.document_sections
  DROP CONSTRAINT IF EXISTS document_sections_level_chk;
ALTER TABLE rag_service.document_sections
  ADD CONSTRAINT document_sections_level_chk CHECK (level IN ('1', '2'));
"""
    )
