"""Fold document_files into documents; drop document_files.

Revision ID: 20260725_drop_document_files
Revises: 20260725_ingest_rename
Create Date: 2026-07-25
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260725_drop_document_files"
down_revision: Union[str, Sequence[str], None] = "20260725_ingest_rename"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
-- Add file columns on documents
ALTER TABLE rag_service.documents
  ADD COLUMN IF NOT EXISTS filename text,
  ADD COLUMN IF NOT EXISTS content_type text;

-- Rename source_uri → storage_key (if still named source_uri)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'rag_service'
      AND table_name = 'documents'
      AND column_name = 'source_uri'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'rag_service'
      AND table_name = 'documents'
      AND column_name = 'storage_key'
  ) THEN
    ALTER TABLE rag_service.documents RENAME COLUMN source_uri TO storage_key;
  ELSIF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'rag_service'
      AND table_name = 'documents'
      AND column_name = 'storage_key'
  ) THEN
    ALTER TABLE rag_service.documents ADD COLUMN storage_key text;
  END IF;
END $$;

-- Backfill from earliest document_files row per doc_id
UPDATE rag_service.documents d
SET
  storage_key = COALESCE(d.storage_key, f.storage_key),
  filename = COALESCE(d.filename, f.filename),
  content_type = COALESCE(d.content_type, f.content_type),
  doc_size = COALESCE(NULLIF(d.doc_size, 0), f.size_bytes, 0),
  source_type = COALESCE(
    d.source_type,
    NULLIF(lower(regexp_replace(f.filename, '^.*\\.', '')), '')
  )
FROM (
  SELECT DISTINCT ON (doc_id)
    doc_id,
    storage_key,
    filename,
    content_type,
    size_bytes
  FROM rag_service.document_files
  ORDER BY doc_id, create_at ASC
) f
WHERE d.doc_id = f.doc_id;

COMMENT ON COLUMN rag_service.documents.storage_key IS
  '对象存储键；每版本至多一个源文件';
COMMENT ON COLUMN rag_service.documents.filename IS
  '原始文件名';
COMMENT ON COLUMN rag_service.documents.content_type IS
  'MIME 类型';

DROP TRIGGER IF EXISTS tr_document_files_lmt ON rag_service.document_files;
DROP TABLE IF EXISTS rag_service.document_files;
"""
    )


def downgrade() -> None:
    op.execute(
        """
CREATE TABLE IF NOT EXISTS rag_service.document_files (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES rag_service.tenants (tenant_id) ON DELETE CASCADE,
  doc_id        uuid NOT NULL REFERENCES rag_service.documents (doc_id) ON DELETE CASCADE,
  version       int NOT NULL DEFAULT 1,
  storage_key   text NOT NULL,
  filename      text NOT NULL,
  content_type  text NOT NULL,
  size_bytes    bigint NOT NULL,
  create_at     timestamp NOT NULL DEFAULT now(),
  update_at     timestamp NOT NULL DEFAULT now(),
  CONSTRAINT document_files_size_chk CHECK (size_bytes <= 20971520)
);

CREATE INDEX IF NOT EXISTS document_files_tenant_document_idx
  ON rag_service.document_files (tenant_id, doc_id);

CREATE INDEX IF NOT EXISTS document_files_document_version_idx
  ON rag_service.document_files (doc_id, version);

DROP TRIGGER IF EXISTS tr_document_files_lmt ON rag_service.document_files;
CREATE TRIGGER tr_document_files_lmt
  BEFORE UPDATE ON rag_service.document_files
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();

-- Restore one file row per document that has storage_key
INSERT INTO rag_service.document_files (
  tenant_id, doc_id, version, storage_key, filename, content_type, size_bytes
)
SELECT
  d.tenant_id,
  d.doc_id,
  d.version_number,
  d.storage_key,
  COALESCE(d.filename, 'unknown'),
  COALESCE(d.content_type, 'application/octet-stream'),
  COALESCE(d.doc_size, 0)
FROM rag_service.documents d
WHERE d.storage_key IS NOT NULL AND d.storage_key <> '';

-- Rename storage_key back to source_uri
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'rag_service'
      AND table_name = 'documents'
      AND column_name = 'storage_key'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'rag_service'
      AND table_name = 'documents'
      AND column_name = 'source_uri'
  ) THEN
    ALTER TABLE rag_service.documents RENAME COLUMN storage_key TO source_uri;
  END IF;
END $$;

ALTER TABLE rag_service.documents DROP COLUMN IF EXISTS filename;
ALTER TABLE rag_service.documents DROP COLUMN IF EXISTS content_type;
"""
    )
