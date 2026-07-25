"""Rename index_jobs/index_status to ingest_jobs/ingest_status.

Revision ID: 20260725_ingest_rename
Revises: 20260724_merge_level_chk_f13
Create Date: 2026-07-25
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260725_ingest_rename"
down_revision: Union[str, Sequence[str], None] = "20260724_merge_level_chk_f13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
-- documents.index_status → ingest_status
ALTER TABLE rag_service.documents
  RENAME COLUMN index_status TO ingest_status;

ALTER TABLE rag_service.documents
  DROP CONSTRAINT IF EXISTS documents_index_status_chk;

ALTER TABLE rag_service.documents
  ADD CONSTRAINT documents_ingest_status_chk CHECK (
    ingest_status IN ('pending', 'processing', 'ready', 'failed')
  );

DROP INDEX IF EXISTS rag_service.documents_tenant_index_status_idx;
DROP INDEX IF EXISTS rag_service.ix_documents_tenant_index_status;

CREATE INDEX ix_documents_tenant_ingest_status
  ON rag_service.documents (tenant_id, ingest_status);

COMMENT ON COLUMN rag_service.documents.ingest_status IS
  '摄入状态：pending / processing / ready / failed';

-- index_jobs → ingest_jobs
ALTER TABLE rag_service.index_jobs RENAME TO ingest_jobs;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'rag_service' AND c.relname = 'index_jobs_pending_idx'
  ) THEN
    ALTER INDEX rag_service.index_jobs_pending_idx RENAME TO ingest_jobs_pending_idx;
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'rag_service'
      AND c.relname = 'index_jobs_tenant_document_version_idx'
  ) THEN
    ALTER INDEX rag_service.index_jobs_tenant_document_version_idx
      RENAME TO ingest_jobs_tenant_document_version_idx;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'index_jobs_status_chk'
      AND conrelid = 'rag_service.ingest_jobs'::regclass
  ) THEN
    ALTER TABLE rag_service.ingest_jobs
      RENAME CONSTRAINT index_jobs_status_chk TO ingest_jobs_status_chk;
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'index_jobs_pkey'
      AND conrelid = 'rag_service.ingest_jobs'::regclass
  ) THEN
    ALTER TABLE rag_service.ingest_jobs
      RENAME CONSTRAINT index_jobs_pkey TO ingest_jobs_pkey;
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'index_jobs_tenant_id_fkey'
      AND conrelid = 'rag_service.ingest_jobs'::regclass
  ) THEN
    ALTER TABLE rag_service.ingest_jobs
      RENAME CONSTRAINT index_jobs_tenant_id_fkey TO ingest_jobs_tenant_id_fkey;
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'index_jobs_doc_id_fkey'
      AND conrelid = 'rag_service.ingest_jobs'::regclass
  ) THEN
    ALTER TABLE rag_service.ingest_jobs
      RENAME CONSTRAINT index_jobs_doc_id_fkey TO ingest_jobs_doc_id_fkey;
  END IF;
END $$;

DROP TRIGGER IF EXISTS tr_index_jobs_lmt ON rag_service.ingest_jobs;
CREATE TRIGGER tr_ingest_jobs_lmt
  BEFORE UPDATE ON rag_service.ingest_jobs
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();

COMMENT ON TABLE rag_service.ingest_jobs IS '文档摄入任务队列';
"""
    )


def downgrade() -> None:
    op.execute(
        """
DROP TRIGGER IF EXISTS tr_ingest_jobs_lmt ON rag_service.ingest_jobs;
CREATE TRIGGER tr_index_jobs_lmt
  BEFORE UPDATE ON rag_service.ingest_jobs
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'ingest_jobs_doc_id_fkey'
      AND conrelid = 'rag_service.ingest_jobs'::regclass
  ) THEN
    ALTER TABLE rag_service.ingest_jobs
      RENAME CONSTRAINT ingest_jobs_doc_id_fkey TO index_jobs_doc_id_fkey;
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'ingest_jobs_tenant_id_fkey'
      AND conrelid = 'rag_service.ingest_jobs'::regclass
  ) THEN
    ALTER TABLE rag_service.ingest_jobs
      RENAME CONSTRAINT ingest_jobs_tenant_id_fkey TO index_jobs_tenant_id_fkey;
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'ingest_jobs_pkey'
      AND conrelid = 'rag_service.ingest_jobs'::regclass
  ) THEN
    ALTER TABLE rag_service.ingest_jobs
      RENAME CONSTRAINT ingest_jobs_pkey TO index_jobs_pkey;
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'ingest_jobs_status_chk'
      AND conrelid = 'rag_service.ingest_jobs'::regclass
  ) THEN
    ALTER TABLE rag_service.ingest_jobs
      RENAME CONSTRAINT ingest_jobs_status_chk TO index_jobs_status_chk;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'rag_service'
      AND c.relname = 'ingest_jobs_tenant_document_version_idx'
  ) THEN
    ALTER INDEX rag_service.ingest_jobs_tenant_document_version_idx
      RENAME TO index_jobs_tenant_document_version_idx;
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'rag_service' AND c.relname = 'ingest_jobs_pending_idx'
  ) THEN
    ALTER INDEX rag_service.ingest_jobs_pending_idx RENAME TO index_jobs_pending_idx;
  END IF;
END $$;

ALTER TABLE rag_service.ingest_jobs RENAME TO index_jobs;

DROP INDEX IF EXISTS rag_service.ix_documents_tenant_ingest_status;

ALTER TABLE rag_service.documents
  DROP CONSTRAINT IF EXISTS documents_ingest_status_chk;

ALTER TABLE rag_service.documents
  RENAME COLUMN ingest_status TO index_status;

ALTER TABLE rag_service.documents
  ADD CONSTRAINT documents_index_status_chk CHECK (
    index_status IN ('pending', 'processing', 'ready', 'failed')
  );

CREATE INDEX ix_documents_tenant_index_status
  ON rag_service.documents (tenant_id, index_status);
"""
    )
