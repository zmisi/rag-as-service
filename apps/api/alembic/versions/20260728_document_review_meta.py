"""Add document review metadata columns.

Revision ID: 20260728_document_review_meta
Revises: 20260727_f02_folder_meta
Create Date: 2026-07-28
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_document_review_meta"
down_revision: Union[str, Sequence[str], None] = "20260727_f02_folder_meta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "rag_service"


def upgrade() -> None:
    """Add reviewer/audit metadata to documents."""
    op.add_column(
        "documents",
        sa.Column("reviewed_by", sa.Uuid(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "documents",
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "documents",
        sa.Column("review_comment", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_documents_reviewed_by_users",
        "documents",
        "users",
        ["reviewed_by"],
        ["user_id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Drop reviewer/audit metadata from documents."""
    op.drop_constraint(
        "fk_documents_reviewed_by_users",
        "documents",
        schema=SCHEMA,
        type_="foreignkey",
    )
    op.drop_column("documents", "review_comment", schema=SCHEMA)
    op.drop_column("documents", "reviewed_at", schema=SCHEMA)
    op.drop_column("documents", "reviewed_by", schema=SCHEMA)
