"""Rename documents file_* columns and reorder physical columns.

Revision ID: 20260725_documents_file_cols
Revises: 20260725_drop_document_files
Create Date: 2026-07-25
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260725_documents_file_cols"
down_revision: Union[str, Sequence[str], None] = "20260725_drop_document_files"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
-- 1) Rename columns (idempotent-ish: only if old names exist)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='rag_service' AND table_name='documents'
               AND column_name='storage_key') THEN
    ALTER TABLE rag_service.documents RENAME COLUMN storage_key TO file_storage_path;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='rag_service' AND table_name='documents'
               AND column_name='doc_size') THEN
    ALTER TABLE rag_service.documents RENAME COLUMN doc_size TO file_size_bytes;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='rag_service' AND table_name='documents'
               AND column_name='filename') THEN
    ALTER TABLE rag_service.documents RENAME COLUMN filename TO file_name;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='rag_service' AND table_name='documents'
               AND column_name='source_type') THEN
    ALTER TABLE rag_service.documents RENAME COLUMN source_type TO file_type;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='rag_service' AND table_name='documents'
               AND column_name='source_modified_at') THEN
    ALTER TABLE rag_service.documents RENAME COLUMN source_modified_at TO file_modified_at;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='rag_service' AND table_name='documents'
               AND column_name='source_metadata') THEN
    ALTER TABLE rag_service.documents RENAME COLUMN source_metadata TO file_metadata;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='rag_service' AND table_name='documents'
               AND column_name='content_type') THEN
    ALTER TABLE rag_service.documents RENAME COLUMN content_type TO file_content_type;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='rag_service' AND table_name='documents'
               AND column_name='content_sha256') THEN
    ALTER TABLE rag_service.documents RENAME COLUMN content_sha256 TO file_content_sha256;
  END IF;
END $$;

-- 2) Rebuild table for physical column order
CREATE TABLE rag_service.documents_new (
  doc_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  doc_name text NOT NULL DEFAULT '',
  doc_tag text NOT NULL DEFAULT '',
  doc_group_id uuid NOT NULL,
  publish_status text NOT NULL,
  ingest_status text NOT NULL,
  error_message text NULL,
  file_name text NULL,
  file_type text NULL,
  file_size_bytes bigint NOT NULL DEFAULT 0,
  file_content_type text NULL,
  file_content_sha256 text NULL,
  file_modified_at timestamp NULL,
  file_storage_path text NULL,
  file_metadata jsonb NULL,
  version_number int NOT NULL,
  is_latest boolean NOT NULL DEFAULT true,
  embedding_provider text NULL,
  embedding_model text NULL,
  embedding_dimension int NULL,
  created_by uuid NOT NULL,
  create_at timestamp NOT NULL DEFAULT now(),
  update_at timestamp NOT NULL DEFAULT now(),
  deleted_at timestamp NULL,
  CONSTRAINT documents_new_publish_status_chk CHECK (
    publish_status IN ('draft', 'review', 'published')
  ),
  CONSTRAINT documents_new_ingest_status_chk CHECK (
    ingest_status IN ('pending', 'processing', 'ready', 'failed')
  )
);

INSERT INTO rag_service.documents_new (
  doc_id, tenant_id, doc_name, doc_tag, doc_group_id,
  publish_status, ingest_status, error_message,
  file_name, file_type, file_size_bytes, file_content_type,
  file_content_sha256, file_modified_at, file_storage_path, file_metadata,
  version_number, is_latest,
  embedding_provider, embedding_model, embedding_dimension,
  created_by, create_at, update_at, deleted_at
)
SELECT
  doc_id, tenant_id, doc_name, doc_tag, doc_group_id,
  publish_status, ingest_status, error_message,
  file_name, file_type, COALESCE(file_size_bytes, 0), file_content_type,
  file_content_sha256, file_modified_at, file_storage_path, file_metadata,
  version_number, is_latest,
  embedding_provider, embedding_model, embedding_dimension,
  created_by, create_at, update_at, deleted_at
FROM rag_service.documents;

-- Drop FKs from child tables that reference documents
ALTER TABLE rag_service.ingest_jobs
  DROP CONSTRAINT IF EXISTS ingest_jobs_doc_id_fkey;
ALTER TABLE rag_service.document_sections
  DROP CONSTRAINT IF EXISTS document_sections_doc_id_fkey;
ALTER TABLE rag_service.document_chunks
  DROP CONSTRAINT IF EXISTS document_chunks_doc_id_fkey;

DROP TRIGGER IF EXISTS tr_documents_lmt ON rag_service.documents;
DROP TABLE rag_service.documents;

ALTER TABLE rag_service.documents_new RENAME TO documents;

ALTER TABLE rag_service.documents
  RENAME CONSTRAINT documents_new_pkey TO pk_documents_doc_id;
ALTER TABLE rag_service.documents
  RENAME CONSTRAINT documents_new_publish_status_chk TO documents_publish_status_chk;
ALTER TABLE rag_service.documents
  RENAME CONSTRAINT documents_new_ingest_status_chk TO documents_ingest_status_chk;

ALTER TABLE rag_service.documents
  ADD CONSTRAINT documents_tenant_id_fkey
  FOREIGN KEY (tenant_id) REFERENCES rag_service.tenants (tenant_id) ON DELETE CASCADE;
ALTER TABLE rag_service.documents
  ADD CONSTRAINT documents_created_by_fkey
  FOREIGN KEY (created_by) REFERENCES rag_service.users (user_id) ON DELETE RESTRICT;

ALTER TABLE rag_service.documents
  ADD CONSTRAINT uk_documents_tenant_group_version
  UNIQUE (tenant_id, doc_group_id, version_number);

ALTER TABLE rag_service.ingest_jobs
  ADD CONSTRAINT ingest_jobs_doc_id_fkey
  FOREIGN KEY (doc_id) REFERENCES rag_service.documents (doc_id) ON DELETE CASCADE;
ALTER TABLE rag_service.document_sections
  ADD CONSTRAINT document_sections_doc_id_fkey
  FOREIGN KEY (doc_id) REFERENCES rag_service.documents (doc_id) ON DELETE CASCADE;
ALTER TABLE rag_service.document_chunks
  ADD CONSTRAINT document_chunks_doc_id_fkey
  FOREIGN KEY (doc_id) REFERENCES rag_service.documents (doc_id) ON DELETE CASCADE;

CREATE TRIGGER tr_documents_lmt
  BEFORE UPDATE ON rag_service.documents
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();

COMMENT ON COLUMN rag_service.documents.file_storage_path IS '对象存储键；每版本至多一个源文件';
COMMENT ON COLUMN rag_service.documents.file_name IS '原始文件名';
COMMENT ON COLUMN rag_service.documents.file_content_type IS 'MIME 类型';
COMMENT ON COLUMN rag_service.documents.file_size_bytes IS '源文件字节数';
COMMENT ON COLUMN rag_service.documents.file_content_sha256 IS '源内容哈希';
"""
    )


def downgrade() -> None:
    op.execute(
        """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='rag_service' AND table_name='documents'
               AND column_name='file_storage_path') THEN
    ALTER TABLE rag_service.documents RENAME COLUMN file_storage_path TO storage_key;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='rag_service' AND table_name='documents'
               AND column_name='file_size_bytes') THEN
    ALTER TABLE rag_service.documents RENAME COLUMN file_size_bytes TO doc_size;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='rag_service' AND table_name='documents'
               AND column_name='file_name') THEN
    ALTER TABLE rag_service.documents RENAME COLUMN file_name TO filename;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='rag_service' AND table_name='documents'
               AND column_name='file_type') THEN
    ALTER TABLE rag_service.documents RENAME COLUMN file_type TO source_type;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='rag_service' AND table_name='documents'
               AND column_name='file_modified_at') THEN
    ALTER TABLE rag_service.documents RENAME COLUMN file_modified_at TO source_modified_at;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='rag_service' AND table_name='documents'
               AND column_name='file_metadata') THEN
    ALTER TABLE rag_service.documents RENAME COLUMN file_metadata TO source_metadata;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='rag_service' AND table_name='documents'
               AND column_name='file_content_type') THEN
    ALTER TABLE rag_service.documents RENAME COLUMN file_content_type TO content_type;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='rag_service' AND table_name='documents'
               AND column_name='file_content_sha256') THEN
    ALTER TABLE rag_service.documents RENAME COLUMN file_content_sha256 TO content_sha256;
  END IF;
END $$;
"""
    )
