"""Drop documents latest UK + source_key; move audit columns to table end.

Revision ID: 20260723_audit_cols_source_key
Revises: 20260723_drop_redundant_indexes
Create Date: 2026-07-23
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260723_audit_cols_source_key"
down_revision: Union[str, Sequence[str], None] = "20260723_drop_redundant_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _move_ts_to_end(table: str, extra_before_ts: list[str] | None = None) -> None:
    """Recreate create_at/update_at (and optional audit cols) at physical end.

    extra_before_ts: columns to also move to end, immediately before create_at/update_at
    (e.g. created_by, deleted_at). Those columns must already exist.
    """
    extras = extra_before_ts or []
    schema_table = f"rag_service.{table}"
    op.execute(f"DROP TRIGGER IF EXISTS tr_{table}_lmt ON {schema_table}")

    # Drop FK on created_by if we are moving it
    if "created_by" in extras:
        op.execute(
            f"ALTER TABLE {schema_table} DROP CONSTRAINT IF EXISTS {table}_created_by_fkey"
        )
        op.execute(
            f"ALTER TABLE {schema_table} DROP CONSTRAINT IF EXISTS documents_created_by_fkey"
        )

    for col in extras:
        if col == "created_by":
            op.execute(
                f"""
ALTER TABLE {schema_table}
  ADD COLUMN IF NOT EXISTS created_by__new uuid;
UPDATE {schema_table} SET created_by__new = created_by;
"""
            )
        elif col == "deleted_at":
            op.execute(
                f"""
ALTER TABLE {schema_table}
  ADD COLUMN IF NOT EXISTS deleted_at__new timestamp NULL;
UPDATE {schema_table} SET deleted_at__new = deleted_at;
"""
            )

    op.execute(
        f"""
ALTER TABLE {schema_table}
  ADD COLUMN IF NOT EXISTS create_at__new timestamp NOT NULL DEFAULT now();
ALTER TABLE {schema_table}
  ADD COLUMN IF NOT EXISTS update_at__new timestamp NOT NULL DEFAULT now();
UPDATE {schema_table}
  SET create_at__new = create_at, update_at__new = update_at;
"""
    )

    for col in extras:
        op.execute(f"ALTER TABLE {schema_table} DROP COLUMN IF EXISTS {col}")
    op.execute(f"ALTER TABLE {schema_table} DROP COLUMN IF EXISTS create_at")
    op.execute(f"ALTER TABLE {schema_table} DROP COLUMN IF EXISTS update_at")

    for col in extras:
        op.execute(
            f"ALTER TABLE {schema_table} RENAME COLUMN {col}__new TO {col}"
        )
    op.execute(
        f"ALTER TABLE {schema_table} RENAME COLUMN create_at__new TO create_at"
    )
    op.execute(
        f"ALTER TABLE {schema_table} RENAME COLUMN update_at__new TO update_at"
    )

    if "created_by" in extras:
        op.execute(
            f"""
ALTER TABLE {schema_table}
  ALTER COLUMN created_by SET NOT NULL;
ALTER TABLE {schema_table}
  ADD CONSTRAINT documents_created_by_fkey
  FOREIGN KEY (created_by) REFERENCES rag_service.users (user_id) ON DELETE RESTRICT;
"""
        )

    op.execute(
        f"""
CREATE TRIGGER tr_{table}_lmt
  BEFORE UPDATE ON {schema_table}
  FOR EACH ROW EXECUTE FUNCTION rag_service.f_common_update_at();
"""
    )


def upgrade() -> None:
    # 1) Drop partial unique on documents.is_latest
    op.execute(
        "DROP INDEX IF EXISTS rag_service.uk_documents_tenant_group_latest"
    )

    # 2) Drop source_key
    op.execute(
        "ALTER TABLE rag_service.documents DROP COLUMN IF EXISTS source_key"
    )

    # 3) Move audit / timestamp columns to physical end on tables that need it
    _move_ts_to_end("users")
    _move_ts_to_end("tenants")
    _move_ts_to_end("tenant_members")
    _move_ts_to_end("documents", extra_before_ts=["created_by", "deleted_at"])
    _move_ts_to_end("document_files")
    _move_ts_to_end("index_jobs")
    _move_ts_to_end("document_chunks")
    _move_ts_to_end("messages")


def downgrade() -> None:
    # Restore source_key + latest UK only (column order not restored).
    op.execute(
        """
ALTER TABLE rag_service.documents
  ADD COLUMN IF NOT EXISTS source_key text NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uk_documents_tenant_group_latest
  ON rag_service.documents (tenant_id, doc_group_id)
  WHERE is_latest = true;
"""
    )
