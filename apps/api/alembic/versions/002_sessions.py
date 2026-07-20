"""sessions table for auth cookies

Revision ID: 002
Revises: 001
Create Date: 2026-07-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "rag_service"


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(), nullable=True),
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
            ["user_id"],
            [f"{SCHEMA}.users.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("token_hash", name="sessions_token_hash_key"),
        schema=SCHEMA,
    )
    op.create_index(
        "sessions_user_id_idx",
        "sessions",
        ["user_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "sessions_expires_at_idx",
        "sessions",
        ["expires_at"],
        schema=SCHEMA,
    )
    op.execute(f"COMMENT ON TABLE {SCHEMA}.sessions IS '服务端会话存储'")
    op.execute(
        f"""
        CREATE TRIGGER tr_sessions_lmt
          BEFORE UPDATE ON {SCHEMA}.sessions
          FOR EACH ROW
          EXECUTE FUNCTION {SCHEMA}.f_common_update_at()
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS tr_sessions_lmt ON {SCHEMA}.sessions")
    op.drop_index("sessions_expires_at_idx", table_name="sessions", schema=SCHEMA)
    op.drop_index("sessions_user_id_idx", table_name="sessions", schema=SCHEMA)
    op.drop_table("sessions", schema=SCHEMA)
