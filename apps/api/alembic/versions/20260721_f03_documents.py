"""F03 documents / document_files / index_jobs schema.

Revision ID: 20260721_f03
Revises: 20260720_f05
Create Date: 2026-07-21

Source: docs/specs/phase1/features/F03-doc-admin.md
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260721_f03"
down_revision: Union[str, Sequence[str], None] = "20260720_f05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE rag_service.documents (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   uuid NOT NULL REFERENCES rag_service.tenants (id) ON DELETE CASCADE,
  title       text NOT NULL DEFAULT '',
  tag         text NOT NULL DEFAULT '',
  status      text NOT NULL DEFAULT 'draft',
  version     text NOT NULL DEFAULT '0.0',
  created_by  uuid NOT NULL REFERENCES rag_service.users (id) ON DELETE RESTRICT,
  deleted_at  timestamp,
  create_at   timestamp NOT NULL DEFAULT now(),
  update_at   timestamp NOT NULL DEFAULT now(),
  CONSTRAINT documents_status_chk CHECK (
    status IN ('draft', 'review', 'published')
  ),
  CONSTRAINT documents_tag_chk CHECK (
    tag IN ('', 'news', 'sop', 'best_practice', 'knowledge_base', 'faq')
  )
);

CREATE INDEX documents_tenant_status_idx
  ON rag_service.documents (tenant_id, status)
  WHERE deleted_at IS NULL;

CREATE INDEX documents_tenant_tag_idx
  ON rag_service.documents (tenant_id, tag)
  WHERE deleted_at IS NULL;

CREATE TRIGGER tr_documents_lmt
  BEFORE UPDATE ON rag_service.documents
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();

CREATE TABLE rag_service.document_files (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES rag_service.tenants (id) ON DELETE CASCADE,
  document_id   uuid NOT NULL REFERENCES rag_service.documents (id) ON DELETE CASCADE,
  version       text NOT NULL DEFAULT '0.0',
  storage_key   text NOT NULL,
  filename      text NOT NULL,
  content_type  text NOT NULL,
  size_bytes    bigint NOT NULL,
  create_at     timestamp NOT NULL DEFAULT now(),
  update_at     timestamp NOT NULL DEFAULT now(),
  CONSTRAINT document_files_size_chk CHECK (size_bytes <= 20971520)
);

CREATE INDEX document_files_tenant_document_idx
  ON rag_service.document_files (tenant_id, document_id);

CREATE INDEX document_files_document_version_idx
  ON rag_service.document_files (document_id, version);

CREATE TRIGGER tr_document_files_lmt
  BEFORE UPDATE ON rag_service.document_files
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();

CREATE TABLE rag_service.index_jobs (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid NOT NULL REFERENCES rag_service.tenants (id) ON DELETE CASCADE,
  document_id    uuid NOT NULL REFERENCES rag_service.documents (id) ON DELETE CASCADE,
  version        text NOT NULL,
  status         text NOT NULL DEFAULT 'pending',
  error          text,
  attempt_count  int NOT NULL DEFAULT 0,
  started_at     timestamp,
  finished_at    timestamp,
  create_at      timestamp NOT NULL DEFAULT now(),
  update_at      timestamp NOT NULL DEFAULT now(),
  CONSTRAINT index_jobs_status_chk CHECK (
    status IN ('pending', 'running', 'succeeded', 'failed')
  )
);

CREATE INDEX index_jobs_pending_idx
  ON rag_service.index_jobs (status, create_at)
  WHERE status = 'pending';

CREATE INDEX index_jobs_tenant_document_version_idx
  ON rag_service.index_jobs (tenant_id, document_id, version);

CREATE TRIGGER tr_index_jobs_lmt
  BEFORE UPDATE ON rag_service.index_jobs
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();
"""
    )


def downgrade() -> None:
    op.execute(
        """
DROP TABLE IF EXISTS rag_service.index_jobs;
DROP TABLE IF EXISTS rag_service.document_files;
DROP TABLE IF EXISTS rag_service.documents;
"""
    )
