"""Add is_hot to faq_suggestion_stats (F13 sticky hot).

Revision ID: 20260724_f13_is_hot
Revises: 20260724_f13_faq_stats
Create Date: 2026-07-24

Source: docs/specs/phase2/features/F13-portal-faq-suggestions.md
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260724_f13_is_hot"
down_revision: Union[str, Sequence[str], None] = "20260724_f13_faq_stats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
ALTER TABLE rag_service.faq_suggestion_stats
  ADD COLUMN is_hot boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN rag_service.faq_suggestion_stats.is_hot IS '运营置顶 Hot；response.hot 透出此字段';
"""
    )


def downgrade() -> None:
    op.execute(
        """
ALTER TABLE rag_service.faq_suggestion_stats
  DROP COLUMN IF EXISTS is_hot;
"""
    )
