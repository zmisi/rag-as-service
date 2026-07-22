"""F04temp: document_chunks + pgvector for F06 e2e search.

Revision ID: 20260722_f04temp
Revises: 20260722_merge_f03_f06
Create Date: 2026-07-22

Temporary branch implementation — not a full Spec-approved F04 delivery.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260722_f04temp"
down_revision: Union[str, Sequence[str], None] = "20260722_merge_f03_f06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Must match rag_api.indexing.constants.EMBEDDING_DIM
_EMBEDDING_DIM = 1024


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        f"""
CREATE TABLE rag_service.document_chunks (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES rag_service.tenants (id) ON DELETE CASCADE,
  document_id   uuid NOT NULL REFERENCES rag_service.documents (id) ON DELETE CASCADE,
  version       text NOT NULL,
  ordinal       int NOT NULL,
  content       text NOT NULL,
  embedding     vector({_EMBEDDING_DIM}) NOT NULL,
  is_active     boolean NOT NULL DEFAULT true,
  create_at     timestamp NOT NULL DEFAULT now(),
  update_at     timestamp NOT NULL DEFAULT now(),
  CONSTRAINT document_chunks_ordinal_chk CHECK (ordinal >= 0)
);

CREATE INDEX document_chunks_tenant_active_idx
  ON rag_service.document_chunks (tenant_id)
  WHERE is_active = true;

CREATE INDEX document_chunks_document_version_idx
  ON rag_service.document_chunks (document_id, version);

CREATE TRIGGER tr_document_chunks_lmt
  BEFORE UPDATE ON rag_service.document_chunks
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();
"""
    )


def downgrade() -> None:
    op.execute(
        """
DROP TRIGGER IF EXISTS tr_document_chunks_lmt ON rag_service.document_chunks;
DROP TABLE IF EXISTS rag_service.document_chunks;
"""
    )
