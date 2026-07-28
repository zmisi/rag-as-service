"""P2-F02: folders.description + folders.visibility metadata.

Revision ID: 20260727_f02_folder_meta
Revises: 20260727_f02_folders
Create Date: 2026-07-27
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260727_f02_folder_meta"
down_revision: Union[str, Sequence[str], None] = "20260727_f02_folders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "rag_service"


def upgrade() -> None:
    """Add description and visibility columns on folders (metadata only; no ACL)."""
    op.add_column(
        "folders",
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "folders",
        sa.Column(
            "visibility",
            sa.Text(),
            nullable=False,
            server_default="private",
        ),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_folders_visibility",
        "folders",
        "visibility IN ('public', 'partial', 'private')",
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Drop description and visibility columns."""
    op.drop_constraint("ck_folders_visibility", "folders", schema=SCHEMA, type_="check")
    op.drop_column("folders", "visibility", schema=SCHEMA)
    op.drop_column("folders", "description", schema=SCHEMA)
