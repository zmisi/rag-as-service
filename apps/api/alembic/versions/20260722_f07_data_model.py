"""F07: document version rows, dual status, is_latest, rich chunks.

Revision ID: 20260722_f07_data_model
Revises: 20260722_f04_sections
Create Date: 2026-07-22
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260722_f07_data_model"
down_revision: Union[str, Sequence[str], None] = "20260722_f04_sections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VERSION_TO_INT = """
CASE
  WHEN version = '0.0' THEN 1
  ELSE COALESCE(NULLIF(split_part(version, '.', 1), '')::int, 1)
END
"""


def upgrade() -> None:
    # --- documents ---
    op.execute(
        f"""
ALTER TABLE rag_service.documents
  RENAME COLUMN status TO publish_status;

ALTER TABLE rag_service.documents
  DROP CONSTRAINT IF EXISTS documents_status_chk;

ALTER TABLE rag_service.documents
  ADD CONSTRAINT documents_publish_status_chk CHECK (
    publish_status IN ('draft', 'review', 'published')
  );

ALTER TABLE rag_service.documents
  ADD COLUMN index_status text NOT NULL DEFAULT 'pending',
  ADD COLUMN error_message text NULL,
  ADD COLUMN document_group_id uuid NULL,
  ADD COLUMN source_key text NULL,
  ADD COLUMN content_sha256 text NULL,
  ADD COLUMN source_type text NULL,
  ADD COLUMN source_uri text NULL,
  ADD COLUMN source_modified_at timestamp NULL,
  ADD COLUMN embedding_provider text NULL,
  ADD COLUMN embedding_model text NULL,
  ADD COLUMN embedding_dimension int NULL,
  ADD COLUMN metadata_ jsonb NULL DEFAULT '{{}}'::jsonb,
  ADD COLUMN is_latest boolean NOT NULL DEFAULT true;

UPDATE rag_service.documents
  SET document_group_id = id
  WHERE document_group_id IS NULL;

ALTER TABLE rag_service.documents
  ALTER COLUMN document_group_id SET NOT NULL;

ALTER TABLE rag_service.documents
  ADD CONSTRAINT documents_index_status_chk CHECK (
    index_status IN ('pending', 'processing', 'ready', 'failed')
  );

ALTER TABLE rag_service.documents
  ADD COLUMN version_int int;

UPDATE rag_service.documents
  SET version_int = {_VERSION_TO_INT};

ALTER TABLE rag_service.documents DROP COLUMN version;
ALTER TABLE rag_service.documents RENAME COLUMN version_int TO version;
ALTER TABLE rag_service.documents
  ALTER COLUMN version SET NOT NULL,
  ALTER COLUMN version SET DEFAULT 1;

DROP INDEX IF EXISTS rag_service.documents_tenant_status_idx;
CREATE INDEX documents_tenant_publish_status_idx
  ON rag_service.documents (tenant_id, publish_status)
  WHERE deleted_at IS NULL;

CREATE INDEX documents_tenant_index_status_idx
  ON rag_service.documents (tenant_id, index_status)
  WHERE deleted_at IS NULL;

CREATE INDEX documents_tenant_source_key_idx
  ON rag_service.documents (tenant_id, source_key);

CREATE UNIQUE INDEX documents_tenant_group_version_key
  ON rag_service.documents (tenant_id, document_group_id, version);

CREATE UNIQUE INDEX documents_tenant_group_latest_key
  ON rag_service.documents (tenant_id, document_group_id)
  WHERE is_latest = true;

CREATE INDEX documents_tenant_group_idx
  ON rag_service.documents (tenant_id, document_group_id);
"""
    )

    # --- document_files.version text → int ---
    op.execute(
        f"""
ALTER TABLE rag_service.document_files
  ADD COLUMN version_int int;

UPDATE rag_service.document_files
  SET version_int = {_VERSION_TO_INT};

ALTER TABLE rag_service.document_files DROP COLUMN version;
ALTER TABLE rag_service.document_files RENAME COLUMN version_int TO version;
ALTER TABLE rag_service.document_files
  ALTER COLUMN version SET NOT NULL,
  ALTER COLUMN version SET DEFAULT 1;
"""
    )

    # --- index_jobs.version text → int ---
    op.execute(
        f"""
ALTER TABLE rag_service.index_jobs
  ADD COLUMN version_int int;

UPDATE rag_service.index_jobs
  SET version_int = {_VERSION_TO_INT};

ALTER TABLE rag_service.index_jobs DROP COLUMN version;
ALTER TABLE rag_service.index_jobs RENAME COLUMN version_int TO version;
ALTER TABLE rag_service.index_jobs
  ALTER COLUMN version SET NOT NULL;
"""
    )

    # --- document_sections ---
    # Old uniqueness was (document_id, version, ordinal). Dropping version can leave
    # duplicate section_index per document_id; clear index rows (reindex after migrate).
    op.execute(
        """
DELETE FROM rag_service.document_chunks;
DELETE FROM rag_service.document_sections;
"""
    )

    op.execute(
        """
ALTER TABLE rag_service.document_sections
  DROP CONSTRAINT IF EXISTS document_sections_doc_version_ordinal_key;
ALTER TABLE rag_service.document_sections
  DROP CONSTRAINT IF EXISTS document_sections_level_chk;
ALTER TABLE rag_service.document_sections
  DROP CONSTRAINT IF EXISTS document_sections_ordinal_chk;

DROP INDEX IF EXISTS rag_service.document_sections_tenant_active_idx;
DROP INDEX IF EXISTS rag_service.document_sections_document_version_idx;

ALTER TABLE rag_service.document_sections
  RENAME COLUMN ordinal TO section_index;
ALTER TABLE rag_service.document_sections
  RENAME COLUMN is_active TO is_latest;

ALTER TABLE rag_service.document_sections
  ALTER COLUMN level TYPE text USING level::text;

ALTER TABLE rag_service.document_sections
  DROP COLUMN version;

ALTER TABLE rag_service.document_sections
  ADD CONSTRAINT document_sections_level_chk CHECK (level IN ('1', '2'));
ALTER TABLE rag_service.document_sections
  ADD CONSTRAINT document_sections_section_index_chk CHECK (section_index >= 0);
ALTER TABLE rag_service.document_sections
  ADD CONSTRAINT document_sections_doc_section_index_key
    UNIQUE (document_id, section_index);

CREATE INDEX document_sections_tenant_latest_idx
  ON rag_service.document_sections (tenant_id)
  WHERE is_latest = true;

CREATE INDEX document_sections_document_id_idx
  ON rag_service.document_sections (document_id);
"""
    )

    # --- document_chunks ---
    op.execute(
        """
DROP INDEX IF EXISTS rag_service.document_chunks_section_ordinal_key;
DROP INDEX IF EXISTS rag_service.document_chunks_tenant_active_idx;
DROP INDEX IF EXISTS rag_service.document_chunks_document_version_idx;

ALTER TABLE rag_service.document_chunks
  DROP CONSTRAINT IF EXISTS document_chunks_ordinal_chk;

ALTER TABLE rag_service.document_chunks
  RENAME COLUMN ordinal TO chunk_index;
ALTER TABLE rag_service.document_chunks
  RENAME COLUMN is_active TO is_latest;

ALTER TABLE rag_service.document_chunks
  DROP COLUMN version;

ALTER TABLE rag_service.document_chunks
  ADD COLUMN heading_path text[] NOT NULL DEFAULT '{}'::text[],
  ADD COLUMN embedding_text text,
  ADD COLUMN chunk_type text NOT NULL DEFAULT 'text',
  ADD COLUMN token_count int NULL,
  ADD COLUMN content_hash text NULL,
  ADD COLUMN content_tsv tsvector NULL,
  ADD COLUMN metadata_ jsonb NULL DEFAULT '{}'::jsonb;

UPDATE rag_service.document_chunks
  SET embedding_text = content
  WHERE embedding_text IS NULL;

ALTER TABLE rag_service.document_chunks
  ALTER COLUMN embedding_text SET NOT NULL,
  ALTER COLUMN embedding_text SET DEFAULT '';

ALTER TABLE rag_service.document_chunks
  ADD CONSTRAINT document_chunks_chunk_index_chk CHECK (chunk_index >= 0);
ALTER TABLE rag_service.document_chunks
  ADD CONSTRAINT document_chunks_chunk_type_chk CHECK (
    chunk_type IN ('text', 'table', 'mixed')
  );
ALTER TABLE rag_service.document_chunks
  ADD CONSTRAINT document_chunks_doc_chunk_index_key
    UNIQUE (document_id, chunk_index);

CREATE INDEX document_chunks_tenant_latest_idx
  ON rag_service.document_chunks (tenant_id)
  WHERE is_latest = true;

CREATE INDEX document_chunks_document_id_idx
  ON rag_service.document_chunks (document_id);

DROP INDEX IF EXISTS rag_service.document_chunks_section_id_idx;
CREATE INDEX document_chunks_section_id_idx
  ON rag_service.document_chunks (section_id);
"""
    )


def downgrade() -> None:
    # Best-effort reverse for local dev; destructive fields may lose data.
    op.execute(
        """
DROP INDEX IF EXISTS rag_service.document_chunks_tenant_latest_idx;
DROP INDEX IF EXISTS rag_service.document_chunks_document_id_idx;
ALTER TABLE rag_service.document_chunks
  DROP CONSTRAINT IF EXISTS document_chunks_doc_chunk_index_key;
ALTER TABLE rag_service.document_chunks
  DROP CONSTRAINT IF EXISTS document_chunks_chunk_type_chk;
ALTER TABLE rag_service.document_chunks
  DROP CONSTRAINT IF EXISTS document_chunks_chunk_index_chk;
ALTER TABLE rag_service.document_chunks
  DROP COLUMN IF EXISTS heading_path,
  DROP COLUMN IF EXISTS embedding_text,
  DROP COLUMN IF EXISTS chunk_type,
  DROP COLUMN IF EXISTS token_count,
  DROP COLUMN IF EXISTS content_hash,
  DROP COLUMN IF EXISTS content_tsv,
  DROP COLUMN IF EXISTS metadata_;
ALTER TABLE rag_service.document_chunks
  ADD COLUMN version text NOT NULL DEFAULT '1';
ALTER TABLE rag_service.document_chunks
  RENAME COLUMN chunk_index TO ordinal;
ALTER TABLE rag_service.document_chunks
  RENAME COLUMN is_latest TO is_active;
ALTER TABLE rag_service.document_chunks
  ADD CONSTRAINT document_chunks_ordinal_chk CHECK (ordinal >= 0);
CREATE UNIQUE INDEX document_chunks_section_ordinal_key
  ON rag_service.document_chunks (section_id, ordinal);
CREATE INDEX document_chunks_tenant_active_idx
  ON rag_service.document_chunks (tenant_id)
  WHERE is_active = true;
CREATE INDEX document_chunks_document_version_idx
  ON rag_service.document_chunks (document_id, version);

DROP INDEX IF EXISTS rag_service.document_sections_tenant_latest_idx;
DROP INDEX IF EXISTS rag_service.document_sections_document_id_idx;
ALTER TABLE rag_service.document_sections
  DROP CONSTRAINT IF EXISTS document_sections_doc_section_index_key;
ALTER TABLE rag_service.document_sections
  DROP CONSTRAINT IF EXISTS document_sections_section_index_chk;
ALTER TABLE rag_service.document_sections
  DROP CONSTRAINT IF EXISTS document_sections_level_chk;
ALTER TABLE rag_service.document_sections
  ADD COLUMN version text NOT NULL DEFAULT '1';
ALTER TABLE rag_service.document_sections
  ALTER COLUMN level TYPE int USING level::int;
ALTER TABLE rag_service.document_sections
  RENAME COLUMN section_index TO ordinal;
ALTER TABLE rag_service.document_sections
  RENAME COLUMN is_latest TO is_active;
ALTER TABLE rag_service.document_sections
  ADD CONSTRAINT document_sections_level_chk CHECK (level IN (1, 2));
ALTER TABLE rag_service.document_sections
  ADD CONSTRAINT document_sections_ordinal_chk CHECK (ordinal >= 0);
ALTER TABLE rag_service.document_sections
  ADD CONSTRAINT document_sections_doc_version_ordinal_key
    UNIQUE (document_id, version, ordinal);
CREATE INDEX document_sections_tenant_active_idx
  ON rag_service.document_sections (tenant_id)
  WHERE is_active = true;
CREATE INDEX document_sections_document_version_idx
  ON rag_service.document_sections (document_id, version);

ALTER TABLE rag_service.index_jobs
  ALTER COLUMN version TYPE text USING version::text;
ALTER TABLE rag_service.document_files
  ALTER COLUMN version TYPE text USING version::text;

DROP INDEX IF EXISTS rag_service.documents_tenant_group_version_key;
DROP INDEX IF EXISTS rag_service.documents_tenant_group_latest_key;
DROP INDEX IF EXISTS rag_service.documents_tenant_group_idx;
DROP INDEX IF EXISTS rag_service.documents_tenant_source_key_idx;
DROP INDEX IF EXISTS rag_service.documents_tenant_index_status_idx;
DROP INDEX IF EXISTS rag_service.documents_tenant_publish_status_idx;

ALTER TABLE rag_service.documents
  DROP CONSTRAINT IF EXISTS documents_index_status_chk;
ALTER TABLE rag_service.documents
  DROP CONSTRAINT IF EXISTS documents_publish_status_chk;
ALTER TABLE rag_service.documents
  DROP COLUMN IF EXISTS index_status,
  DROP COLUMN IF EXISTS error_message,
  DROP COLUMN IF EXISTS document_group_id,
  DROP COLUMN IF EXISTS source_key,
  DROP COLUMN IF EXISTS content_sha256,
  DROP COLUMN IF EXISTS source_type,
  DROP COLUMN IF EXISTS source_uri,
  DROP COLUMN IF EXISTS source_modified_at,
  DROP COLUMN IF EXISTS embedding_provider,
  DROP COLUMN IF EXISTS embedding_model,
  DROP COLUMN IF EXISTS embedding_dimension,
  DROP COLUMN IF EXISTS metadata_,
  DROP COLUMN IF EXISTS is_latest;
ALTER TABLE rag_service.documents
  ALTER COLUMN version TYPE text USING version::text;
ALTER TABLE rag_service.documents
  RENAME COLUMN publish_status TO status;
ALTER TABLE rag_service.documents
  ADD CONSTRAINT documents_status_chk CHECK (
    status IN ('draft', 'review', 'published')
  );
CREATE INDEX documents_tenant_status_idx
  ON rag_service.documents (tenant_id, status)
  WHERE deleted_at IS NULL;
"""
    )
