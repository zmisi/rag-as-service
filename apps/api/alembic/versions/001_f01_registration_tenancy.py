"""F01 registration tenancy tables

Revision ID: 001
Revises:
Create Date: 2026-07-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "rag_service"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.f_common_update_at()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.update_at := now();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        f"""
        COMMENT ON FUNCTION {SCHEMA}.f_common_update_at() IS
          'BEFORE UPDATE：仅刷新 update_at，不修改 create_at'
        """
    )

    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
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
        sa.UniqueConstraint("email", name="users_email_key"),
        schema=SCHEMA,
    )
    op.execute(f"COMMENT ON TABLE {SCHEMA}.users IS '平台用户；email 全局唯一'")
    op.execute(
        f"""
        CREATE TRIGGER tr_users_lmt
          BEFORE UPDATE ON {SCHEMA}.users
          FOR EACH ROW
          EXECUTE FUNCTION {SCHEMA}.f_common_update_at()
        """
    )

    op.create_table(
        "tenants",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("subdomain", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("subdomain", name="tenants_subdomain_key"),
        sa.CheckConstraint(
            "char_length(subdomain) BETWEEN 3 AND 32",
            name="tenants_subdomain_length_chk",
        ),
        sa.CheckConstraint(
            "subdomain ~ '^[a-z0-9]([a-z0-9-]*[a-z0-9])?$'",
            name="tenants_subdomain_format_chk",
        ),
        schema=SCHEMA,
    )
    op.execute(
        f"""
        CREATE TRIGGER tr_tenants_lmt
          BEFORE UPDATE ON {SCHEMA}.tenants
          FOR EACH ROW
          EXECUTE FUNCTION {SCHEMA}.f_common_update_at()
        """
    )

    op.create_table(
        "tenant_members",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            [f"{SCHEMA}.tenants.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            [f"{SCHEMA}.users.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "user_id",
            name="tenant_members_tenant_user_key",
        ),
        sa.CheckConstraint("role IN ('owner')", name="tenant_members_role_chk"),
        schema=SCHEMA,
    )
    op.create_index(
        "tenant_members_user_id_idx",
        "tenant_members",
        ["user_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "tenant_members_tenant_id_idx",
        "tenant_members",
        ["tenant_id"],
        schema=SCHEMA,
    )
    op.execute(
        f"""
        CREATE TRIGGER tr_tenant_members_lmt
          BEFORE UPDATE ON {SCHEMA}.tenant_members
          FOR EACH ROW
          EXECUTE FUNCTION {SCHEMA}.f_common_update_at()
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS tr_tenant_members_lmt ON {SCHEMA}.tenant_members")
    op.drop_index("tenant_members_tenant_id_idx", table_name="tenant_members", schema=SCHEMA)
    op.drop_index("tenant_members_user_id_idx", table_name="tenant_members", schema=SCHEMA)
    op.drop_table("tenant_members", schema=SCHEMA)

    op.execute(f"DROP TRIGGER IF EXISTS tr_tenants_lmt ON {SCHEMA}.tenants")
    op.drop_table("tenants", schema=SCHEMA)

    op.execute(f"DROP TRIGGER IF EXISTS tr_users_lmt ON {SCHEMA}.users")
    op.drop_table("users", schema=SCHEMA)

    op.execute(f"DROP FUNCTION IF EXISTS {SCHEMA}.f_common_update_at()")
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
