"""P2-F02: folders table + documents.folder_id.

Revision ID: 20260727_f02_folders
Revises: 20260724_f11_api_keys, 20260725_documents_pk_name
Create Date: 2026-07-27
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260727_f02_folders"
down_revision: Union[str, Sequence[str], None] = (
    "20260724_f11_api_keys",
    "20260725_documents_pk_name",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "rag_service"


def upgrade() -> None:
    """Create folders table, add documents.folder_id, triggers and constraints."""
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.create_table(
        "folders",
        sa.Column(
            "folder_id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.tenants.tenant_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.folders.folder_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "create_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "update_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        schema=SCHEMA,
    )

    # Unique constraint: (tenant_id, parent_id, lower(name))
    # parent_id NULL = root; use COALESCE so NULL parents share uniqueness
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_folders_tenant_parent_name
        ON {SCHEMA}.folders (tenant_id, COALESCE(parent_id, '00000000-0000-0000-0000-000000000000'::uuid), lower(name))
        """
    )

    # update_at trigger
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.f_common_update_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.update_at := now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER tr_folders_lmt
        BEFORE UPDATE ON {SCHEMA}.folders
        FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.f_common_update_at();
        """
    )

    # Add folder_id to documents
    op.add_column(
        "documents",
        sa.Column(
            "folder_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.folders.folder_id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Remove documents.folder_id and drop folders table."""
    op.drop_column("documents", "folder_id", schema=SCHEMA)
    op.execute(f"DROP TRIGGER IF EXISTS tr_folders_lmt ON {SCHEMA}.folders")
    op.execute(f"DROP INDEX IF EXISTS {SCHEMA}.uq_folders_tenant_parent_name")
    op.drop_table("folders", schema=SCHEMA)
