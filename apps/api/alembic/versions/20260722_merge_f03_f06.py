"""Merge F03 documents and F06 agent migration heads.

Revision ID: 20260722_merge_f03_f06
Revises: 20260721_f03, 20260721_f06
Create Date: 2026-07-22
"""

from __future__ import annotations

from typing import Sequence, Union

revision: str = "20260722_merge_f03_f06"
down_revision: Union[str, Sequence[str], None] = ("20260721_f03", "20260721_f06")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
