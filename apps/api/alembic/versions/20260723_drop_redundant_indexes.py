"""Drop redundant indexes on documents / document_chunks / agent_run_steps.

Revision ID: 20260723_drop_redundant_indexes
Revises: 20260723_f08_naming
Create Date: 2026-07-23
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260723_drop_redundant_indexes"
down_revision: Union[str, Sequence[str], None] = "20260723_f08_naming"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) document_chunks: drop all indexes named document_chunks_*
    # Unique constraint duplicate of uk_document_chunks_doc_id_chunk_index
    op.execute(
        """
ALTER TABLE rag_service.document_chunks
  DROP CONSTRAINT IF EXISTS document_chunks_doc_chunk_index_key;
DROP INDEX IF EXISTS rag_service.document_chunks_doc_chunk_index_key;
DROP INDEX IF EXISTS rag_service.document_chunks_document_id_idx;
DROP INDEX IF EXISTS rag_service.document_chunks_section_id_idx;
DROP INDEX IF EXISTS rag_service.document_chunks_tenant_latest_idx;
"""
    )

    # 2) agent_run_steps: redundant with UNIQUE (agent_run_id, step_index)
    op.execute(
        "DROP INDEX IF EXISTS rag_service.agent_run_steps_run_index_idx;"
    )

    # 3) documents: drop all ix_* secondary indexes (keep pk_ / uk_)
    op.execute(
        """
DROP INDEX IF EXISTS rag_service.ix_documents_tenant_content_sha256;
DROP INDEX IF EXISTS rag_service.ix_documents_tenant_doc_tag;
DROP INDEX IF EXISTS rag_service.ix_documents_tenant_group;
DROP INDEX IF EXISTS rag_service.ix_documents_tenant_index_status;
DROP INDEX IF EXISTS rag_service.ix_documents_tenant_publish_status;
DROP INDEX IF EXISTS rag_service.ix_documents_tenant_source_key;
"""
    )


def downgrade() -> None:
    op.execute(
        """
CREATE INDEX IF NOT EXISTS ix_documents_tenant_publish_status
  ON rag_service.documents (tenant_id, publish_status)
  WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_documents_tenant_index_status
  ON rag_service.documents (tenant_id, index_status)
  WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_documents_tenant_source_key
  ON rag_service.documents (tenant_id, source_key);
CREATE INDEX IF NOT EXISTS ix_documents_tenant_group
  ON rag_service.documents (tenant_id, doc_group_id);
CREATE INDEX IF NOT EXISTS ix_documents_tenant_doc_tag
  ON rag_service.documents (tenant_id, doc_tag)
  WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_documents_tenant_content_sha256
  ON rag_service.documents (tenant_id, content_sha256);

CREATE INDEX IF NOT EXISTS agent_run_steps_run_index_idx
  ON rag_service.agent_run_steps (agent_run_id, step_index);

CREATE INDEX IF NOT EXISTS document_chunks_tenant_latest_idx
  ON rag_service.document_chunks (tenant_id)
  WHERE is_latest = true;
CREATE INDEX IF NOT EXISTS document_chunks_document_id_idx
  ON rag_service.document_chunks (doc_id);
CREATE INDEX IF NOT EXISTS document_chunks_section_id_idx
  ON rag_service.document_chunks (section_id);
ALTER TABLE rag_service.document_chunks
  DROP CONSTRAINT IF EXISTS document_chunks_doc_chunk_index_key;
ALTER TABLE rag_service.document_chunks
  ADD CONSTRAINT document_chunks_doc_chunk_index_key
  UNIQUE (doc_id, chunk_index);
"""
    )
