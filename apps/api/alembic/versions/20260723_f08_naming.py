"""F08: data-model naming refactor (PKs, tenant_name, doc_*).

Revision ID: 20260723_f08_naming
Revises: 20260722_f07_data_model
Create Date: 2026-07-23
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260723_f08_naming"
down_revision: Union[str, Sequence[str], None] = "20260722_f07_data_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop FKs that reference tenants.id / users.id / documents.id so PK renames succeed.
    op.execute(
        """
DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT con.conname AS cname, rel.relname AS tname
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
    WHERE nsp.nspname = 'rag_service'
      AND con.contype = 'f'
      AND (
        con.confrelid = 'rag_service.tenants'::regclass
        OR con.confrelid = 'rag_service.users'::regclass
        OR con.confrelid = 'rag_service.documents'::regclass
      )
  LOOP
    EXECUTE format('ALTER TABLE rag_service.%I DROP CONSTRAINT IF EXISTS %I', r.tname, r.cname);
  END LOOP;
END $$;
"""
    )

    # --- tenants ---
    op.execute(
        """
ALTER TABLE rag_service.tenants RENAME COLUMN id TO tenant_id;
ALTER TABLE rag_service.tenants RENAME COLUMN subdomain TO tenant_name;
ALTER TABLE rag_service.tenants DROP COLUMN IF EXISTS display_name;

ALTER TABLE rag_service.tenants
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active',
  ADD COLUMN IF NOT EXISTS charge_mode text NOT NULL DEFAULT 'free';

ALTER TABLE rag_service.tenants DROP CONSTRAINT IF EXISTS tenants_pkey;
ALTER TABLE rag_service.tenants
  ADD CONSTRAINT pk_tenants_tenant_id PRIMARY KEY (tenant_id);

ALTER TABLE rag_service.tenants DROP CONSTRAINT IF EXISTS tenants_subdomain_key;
ALTER TABLE rag_service.tenants DROP CONSTRAINT IF EXISTS tenants_tenant_name_key;
ALTER TABLE rag_service.tenants DROP CONSTRAINT IF EXISTS uk_tenants_tenant_name;
ALTER TABLE rag_service.tenants
  ADD CONSTRAINT uk_tenants_tenant_name UNIQUE (tenant_name);

ALTER TABLE rag_service.tenants DROP CONSTRAINT IF EXISTS tenants_subdomain_length_chk;
ALTER TABLE rag_service.tenants DROP CONSTRAINT IF EXISTS tenants_tenant_name_length_chk;
ALTER TABLE rag_service.tenants
  ADD CONSTRAINT tenants_tenant_name_length_chk
  CHECK (char_length(tenant_name) BETWEEN 3 AND 32);

ALTER TABLE rag_service.tenants DROP CONSTRAINT IF EXISTS tenants_subdomain_format_chk;
ALTER TABLE rag_service.tenants DROP CONSTRAINT IF EXISTS tenants_tenant_name_format_chk;
ALTER TABLE rag_service.tenants
  ADD CONSTRAINT tenants_tenant_name_format_chk
  CHECK (tenant_name ~ '^[a-z0-9]([a-z0-9-]*[a-z0-9])?$');

ALTER TABLE rag_service.tenants DROP CONSTRAINT IF EXISTS tenants_status_chk;
ALTER TABLE rag_service.tenants
  ADD CONSTRAINT tenants_status_chk CHECK (status IN ('active', 'suspended'));

ALTER TABLE rag_service.tenants DROP CONSTRAINT IF EXISTS tenants_charge_mode_chk;
ALTER TABLE rag_service.tenants
  ADD CONSTRAINT tenants_charge_mode_chk CHECK (charge_mode IN ('free', 'standard'));
"""
    )

    # --- users ---
    op.execute(
        """
ALTER TABLE rag_service.users RENAME COLUMN id TO user_id;

ALTER TABLE rag_service.users
  ADD COLUMN IF NOT EXISTS user_name text,
  ADD COLUMN IF NOT EXISTS active int NOT NULL DEFAULT 1;

UPDATE rag_service.users
SET user_name = lower(split_part(email, '@', 1)) || '_' || substr(replace(user_id::text, '-', ''), 1, 8)
WHERE user_name IS NULL;

ALTER TABLE rag_service.users ALTER COLUMN user_name SET NOT NULL;

ALTER TABLE rag_service.users DROP CONSTRAINT IF EXISTS users_pkey;
ALTER TABLE rag_service.users
  ADD CONSTRAINT pk_users_user_id PRIMARY KEY (user_id);

ALTER TABLE rag_service.users DROP CONSTRAINT IF EXISTS users_email_key;
ALTER TABLE rag_service.users DROP CONSTRAINT IF EXISTS uk_users_email;
ALTER TABLE rag_service.users
  ADD CONSTRAINT uk_users_email UNIQUE (email);

ALTER TABLE rag_service.users DROP CONSTRAINT IF EXISTS uk_users_user_name;
ALTER TABLE rag_service.users
  ADD CONSTRAINT uk_users_user_name UNIQUE (user_name);

ALTER TABLE rag_service.users DROP CONSTRAINT IF EXISTS users_active_chk;
ALTER TABLE rag_service.users
  ADD CONSTRAINT users_active_chk CHECK (active IN (0, 1));
"""
    )

    # --- tenant_members ---
    op.execute(
        """
ALTER TABLE rag_service.tenant_members RENAME COLUMN id TO member_id;

ALTER TABLE rag_service.tenant_members
  ADD COLUMN IF NOT EXISTS member_name text,
  ADD COLUMN IF NOT EXISTS active int NOT NULL DEFAULT 1;

UPDATE rag_service.tenant_members tm
SET member_name = u.user_name
FROM rag_service.users u
WHERE tm.user_id = u.user_id
  AND tm.member_name IS NULL;

UPDATE rag_service.tenant_members
SET member_name = 'member_' || substr(replace(member_id::text, '-', ''), 1, 8)
WHERE member_name IS NULL;

ALTER TABLE rag_service.tenant_members ALTER COLUMN member_name SET NOT NULL;

ALTER TABLE rag_service.tenant_members DROP CONSTRAINT IF EXISTS tenant_members_pkey;
ALTER TABLE rag_service.tenant_members
  ADD CONSTRAINT pk_tenant_members_member_id PRIMARY KEY (member_id);

ALTER TABLE rag_service.tenant_members
  DROP CONSTRAINT IF EXISTS tenant_members_tenant_user_key;
ALTER TABLE rag_service.tenant_members
  DROP CONSTRAINT IF EXISTS uk_tenant_members_tenant_id_user_id;
ALTER TABLE rag_service.tenant_members
  ADD CONSTRAINT uk_tenant_members_tenant_id_user_id UNIQUE (tenant_id, user_id);

ALTER TABLE rag_service.tenant_members
  DROP CONSTRAINT IF EXISTS uk_tenant_members_tenant_id_member_name;
ALTER TABLE rag_service.tenant_members
  ADD CONSTRAINT uk_tenant_members_tenant_id_member_name UNIQUE (tenant_id, member_name);

ALTER TABLE rag_service.tenant_members DROP CONSTRAINT IF EXISTS tenant_members_active_chk;
ALTER TABLE rag_service.tenant_members
  ADD CONSTRAINT tenant_members_active_chk CHECK (active IN (0, 1));

DROP INDEX IF EXISTS rag_service.tenant_members_user_id_idx;
DROP INDEX IF EXISTS rag_service.ix_tenant_members_user_id;
CREATE INDEX ix_tenant_members_user_id ON rag_service.tenant_members (user_id);
"""
    )

    # --- documents ---
    op.execute(
        """
ALTER TABLE rag_service.documents RENAME COLUMN id TO doc_id;
ALTER TABLE rag_service.documents RENAME COLUMN title TO doc_name;
ALTER TABLE rag_service.documents RENAME COLUMN tag TO doc_tag;
ALTER TABLE rag_service.documents RENAME COLUMN document_group_id TO doc_group_id;
ALTER TABLE rag_service.documents RENAME COLUMN version TO version_number;
ALTER TABLE rag_service.documents RENAME COLUMN metadata_ TO source_metadata;

ALTER TABLE rag_service.documents
  ADD COLUMN IF NOT EXISTS doc_size bigint NOT NULL DEFAULT 0;

UPDATE rag_service.documents d
SET doc_size = COALESCE((
  SELECT SUM(f.size_bytes)::bigint
  FROM rag_service.document_files f
  WHERE f.document_id = d.doc_id
), 0);

ALTER TABLE rag_service.documents DROP CONSTRAINT IF EXISTS documents_pkey;
ALTER TABLE rag_service.documents
  ADD CONSTRAINT pk_documents_doc_id PRIMARY KEY (doc_id);

DROP INDEX IF EXISTS rag_service.documents_tenant_group_version_key;
DROP INDEX IF EXISTS rag_service.uk_documents_tenant_group_version;
CREATE UNIQUE INDEX uk_documents_tenant_group_version
  ON rag_service.documents (tenant_id, doc_group_id, version_number);

DROP INDEX IF EXISTS rag_service.documents_tenant_group_latest_key;
DROP INDEX IF EXISTS rag_service.uk_documents_tenant_group_latest;
CREATE UNIQUE INDEX uk_documents_tenant_group_latest
  ON rag_service.documents (tenant_id, doc_group_id)
  WHERE is_latest = true;

DROP INDEX IF EXISTS rag_service.documents_tenant_publish_status_idx;
DROP INDEX IF EXISTS rag_service.ix_documents_tenant_publish_status;
CREATE INDEX ix_documents_tenant_publish_status
  ON rag_service.documents (tenant_id, publish_status)
  WHERE deleted_at IS NULL;

DROP INDEX IF EXISTS rag_service.documents_tenant_index_status_idx;
DROP INDEX IF EXISTS rag_service.ix_documents_tenant_index_status;
CREATE INDEX ix_documents_tenant_index_status
  ON rag_service.documents (tenant_id, index_status)
  WHERE deleted_at IS NULL;

DROP INDEX IF EXISTS rag_service.documents_tenant_source_key_idx;
DROP INDEX IF EXISTS rag_service.ix_documents_tenant_source_key;
CREATE INDEX ix_documents_tenant_source_key
  ON rag_service.documents (tenant_id, source_key);

DROP INDEX IF EXISTS rag_service.documents_tenant_group_idx;
DROP INDEX IF EXISTS rag_service.ix_documents_tenant_group;
CREATE INDEX ix_documents_tenant_group
  ON rag_service.documents (tenant_id, doc_group_id);

DROP INDEX IF EXISTS rag_service.documents_tenant_tag_idx;
DROP INDEX IF EXISTS rag_service.ix_documents_tenant_doc_tag;
CREATE INDEX ix_documents_tenant_doc_tag
  ON rag_service.documents (tenant_id, doc_tag)
  WHERE deleted_at IS NULL;

DROP INDEX IF EXISTS rag_service.documents_tenant_content_sha256_idx;
DROP INDEX IF EXISTS rag_service.ix_documents_tenant_content_sha256;
CREATE INDEX ix_documents_tenant_content_sha256
  ON rag_service.documents (tenant_id, content_sha256);
"""
    )

    # --- cascade document_id → doc_id ---
    op.execute(
        """
ALTER TABLE rag_service.document_files RENAME COLUMN document_id TO doc_id;
ALTER TABLE rag_service.document_sections RENAME COLUMN document_id TO doc_id;
ALTER TABLE rag_service.index_jobs RENAME COLUMN document_id TO doc_id;
ALTER TABLE rag_service.document_chunks RENAME COLUMN id TO chunk_id;
ALTER TABLE rag_service.document_chunks RENAME COLUMN document_id TO doc_id;

ALTER TABLE rag_service.document_chunks DROP CONSTRAINT IF EXISTS document_chunks_pkey;
ALTER TABLE rag_service.document_chunks
  ADD CONSTRAINT pk_document_chunks_chunk_id PRIMARY KEY (chunk_id);

DROP INDEX IF EXISTS rag_service.document_chunks_document_id_chunk_index_key;
DROP INDEX IF EXISTS rag_service.uk_document_chunks_doc_id_chunk_index;
CREATE UNIQUE INDEX uk_document_chunks_doc_id_chunk_index
  ON rag_service.document_chunks (doc_id, chunk_index);
"""
    )

    # Recreate FKs to new PK column names
    op.execute(
        """
ALTER TABLE rag_service.tenant_members
  ADD CONSTRAINT tenant_members_tenant_id_fkey
  FOREIGN KEY (tenant_id) REFERENCES rag_service.tenants (tenant_id) ON DELETE CASCADE;
ALTER TABLE rag_service.tenant_members
  ADD CONSTRAINT tenant_members_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES rag_service.users (user_id) ON DELETE CASCADE;

ALTER TABLE rag_service.sessions
  ADD CONSTRAINT sessions_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES rag_service.users (user_id) ON DELETE CASCADE;

ALTER TABLE rag_service.conversations
  ADD CONSTRAINT conversations_tenant_id_fkey
  FOREIGN KEY (tenant_id) REFERENCES rag_service.tenants (tenant_id) ON DELETE CASCADE;
ALTER TABLE rag_service.conversations
  ADD CONSTRAINT conversations_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES rag_service.users (user_id) ON DELETE CASCADE;

ALTER TABLE rag_service.messages
  ADD CONSTRAINT messages_tenant_id_fkey
  FOREIGN KEY (tenant_id) REFERENCES rag_service.tenants (tenant_id) ON DELETE CASCADE;

ALTER TABLE rag_service.agent_runs
  ADD CONSTRAINT agent_runs_tenant_id_fkey
  FOREIGN KEY (tenant_id) REFERENCES rag_service.tenants (tenant_id) ON DELETE CASCADE;

ALTER TABLE rag_service.agent_run_steps
  ADD CONSTRAINT agent_run_steps_tenant_id_fkey
  FOREIGN KEY (tenant_id) REFERENCES rag_service.tenants (tenant_id) ON DELETE CASCADE;

ALTER TABLE rag_service.documents
  ADD CONSTRAINT documents_tenant_id_fkey
  FOREIGN KEY (tenant_id) REFERENCES rag_service.tenants (tenant_id) ON DELETE CASCADE;
ALTER TABLE rag_service.documents
  ADD CONSTRAINT documents_created_by_fkey
  FOREIGN KEY (created_by) REFERENCES rag_service.users (user_id) ON DELETE RESTRICT;

ALTER TABLE rag_service.document_files
  ADD CONSTRAINT document_files_tenant_id_fkey
  FOREIGN KEY (tenant_id) REFERENCES rag_service.tenants (tenant_id) ON DELETE CASCADE;
ALTER TABLE rag_service.document_files
  ADD CONSTRAINT document_files_doc_id_fkey
  FOREIGN KEY (doc_id) REFERENCES rag_service.documents (doc_id) ON DELETE CASCADE;

ALTER TABLE rag_service.document_sections
  ADD CONSTRAINT document_sections_tenant_id_fkey
  FOREIGN KEY (tenant_id) REFERENCES rag_service.tenants (tenant_id) ON DELETE CASCADE;
ALTER TABLE rag_service.document_sections
  ADD CONSTRAINT document_sections_doc_id_fkey
  FOREIGN KEY (doc_id) REFERENCES rag_service.documents (doc_id) ON DELETE CASCADE;

ALTER TABLE rag_service.index_jobs
  ADD CONSTRAINT index_jobs_tenant_id_fkey
  FOREIGN KEY (tenant_id) REFERENCES rag_service.tenants (tenant_id) ON DELETE CASCADE;
ALTER TABLE rag_service.index_jobs
  ADD CONSTRAINT index_jobs_doc_id_fkey
  FOREIGN KEY (doc_id) REFERENCES rag_service.documents (doc_id) ON DELETE CASCADE;

ALTER TABLE rag_service.document_chunks
  ADD CONSTRAINT document_chunks_tenant_id_fkey
  FOREIGN KEY (tenant_id) REFERENCES rag_service.tenants (tenant_id) ON DELETE CASCADE;
ALTER TABLE rag_service.document_chunks
  ADD CONSTRAINT document_chunks_doc_id_fkey
  FOREIGN KEY (doc_id) REFERENCES rag_service.documents (doc_id) ON DELETE CASCADE;
"""
    )


def downgrade() -> None:
    raise NotImplementedError("F08 naming refactor is destructive; rebuild DB to roll back")
