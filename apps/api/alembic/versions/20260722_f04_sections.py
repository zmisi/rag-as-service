"""F04: document_sections + document_chunks.section_id.

Revision ID: 20260722_f04_sections
Revises: 20260722_f04temp
Create Date: 2026-07-22
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260722_f04_sections"
down_revision: Union[str, Sequence[str], None] = "20260722_f04temp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing F04temp chunks lack section_id; clear for reindex after migration.
    op.execute("DELETE FROM rag_service.document_chunks")

    op.execute(
        """
CREATE TABLE rag_service.document_sections (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES rag_service.tenants (id) ON DELETE CASCADE,
  document_id   uuid NOT NULL REFERENCES rag_service.documents (id) ON DELETE CASCADE,
  version       text NOT NULL,
  parent_id     uuid NULL REFERENCES rag_service.document_sections (id) ON DELETE CASCADE,
  level         int NOT NULL,
  title         text NOT NULL,
  path          text NOT NULL,
  content       text NOT NULL,
  ordinal       int NOT NULL,
  is_active     boolean NOT NULL DEFAULT true,
  create_at     timestamp NOT NULL DEFAULT now(),
  update_at     timestamp NOT NULL DEFAULT now(),
  CONSTRAINT document_sections_level_chk CHECK (level IN (1, 2)),
  CONSTRAINT document_sections_ordinal_chk CHECK (ordinal >= 0),
  CONSTRAINT document_sections_doc_version_ordinal_key
    UNIQUE (document_id, version, ordinal)
);

CREATE INDEX document_sections_tenant_active_idx
  ON rag_service.document_sections (tenant_id)
  WHERE is_active = true;

CREATE INDEX document_sections_document_version_idx
  ON rag_service.document_sections (document_id, version);

CREATE TRIGGER tr_document_sections_lmt
  BEFORE UPDATE ON rag_service.document_sections
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();
"""
    )

    op.execute(
        """
ALTER TABLE rag_service.document_chunks
  ADD COLUMN section_id uuid NOT NULL
    REFERENCES rag_service.document_sections (id) ON DELETE CASCADE;

CREATE UNIQUE INDEX document_chunks_section_ordinal_key
  ON rag_service.document_chunks (section_id, ordinal);

CREATE INDEX document_chunks_section_id_idx
  ON rag_service.document_chunks (section_id);
"""
    )


def downgrade() -> None:
    op.execute(
        """
DROP INDEX IF EXISTS rag_service.document_chunks_section_ordinal_key;
DROP INDEX IF EXISTS rag_service.document_chunks_section_id_idx;
ALTER TABLE rag_service.document_chunks DROP COLUMN IF EXISTS section_id;
DROP TRIGGER IF EXISTS tr_document_sections_lmt ON rag_service.document_sections;
DROP TABLE IF EXISTS rag_service.document_sections;
"""
    )
