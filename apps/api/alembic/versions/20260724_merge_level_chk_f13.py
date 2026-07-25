"""Merge 20260724 branch tips (level_chk drop + F13 faq stats).

Revision ID: 20260724_merge_level_chk_f13
Revises: 20260724_drop_sections_level_chk, 20260724_f13_faq_stats
Create Date: 2026-07-24
"""

from __future__ import annotations

from typing import Sequence, Union

revision: str = "20260724_merge_level_chk_f13"
down_revision: Union[str, Sequence[str], None] = (
    "20260724_drop_sections_level_chk",
    "20260724_f13_faq_stats",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
