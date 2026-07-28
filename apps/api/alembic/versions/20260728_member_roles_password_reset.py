"""Add member roles and first-login password reset support.

Revision ID: 20260728_f14_member_auth
Revises: 20260728_document_review_meta
Create Date: 2026-07-28
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_f14_member_auth"
down_revision: Union[str, Sequence[str], None] = "20260728_document_review_meta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "rag_service"


def upgrade() -> None:
    """Add users.must_change_password and expand tenant member roles."""
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema=SCHEMA,
    )
    op.drop_constraint(
        "tenant_members_role_chk",
        "tenant_members",
        schema=SCHEMA,
        type_="check",
    )
    op.create_check_constraint(
        "tenant_members_role_chk",
        "tenant_members",
        "role IN ('owner', 'admin', 'member')",
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Drop first-login flag and restore owner-only role constraint."""
    op.drop_constraint(
        "tenant_members_role_chk",
        "tenant_members",
        schema=SCHEMA,
        type_="check",
    )
    op.create_check_constraint(
        "tenant_members_role_chk",
        "tenant_members",
        "role IN ('owner')",
        schema=SCHEMA,
    )
    op.drop_column("users", "must_change_password", schema=SCHEMA)
