"""Rename documents PK constraint to pk_documents_doc_id.

Revision ID: 20260725_documents_pk_name
Revises: 20260725_documents_file_cols
Create Date: 2026-07-25
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260725_documents_pk_name"
down_revision: Union[str, Sequence[str], None] = "20260725_documents_file_cols"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'documents_new_pkey'
  ) THEN
    ALTER TABLE rag_service.documents
      RENAME CONSTRAINT documents_new_pkey TO pk_documents_doc_id;
  END IF;
END $$;
"""
    )


def downgrade() -> None:
    op.execute(
        """
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'pk_documents_doc_id'
      AND conrelid = 'rag_service.documents'::regclass
  ) THEN
    ALTER TABLE rag_service.documents
      RENAME CONSTRAINT pk_documents_doc_id TO documents_new_pkey;
  END IF;
END $$;
"""
    )
