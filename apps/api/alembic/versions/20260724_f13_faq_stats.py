"""F13 faq_suggestion_stats for Portal FAQ click heat.

Revision ID: 20260724_f13_faq_stats
Revises: 20260723_audit_cols_source_key
Create Date: 2026-07-24

Source: docs/specs/phase2/features/F13-portal-faq-suggestions.md
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260724_f13_faq_stats"
down_revision: Union[str, Sequence[str], None] = "20260723_audit_cols_source_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE rag_service.faq_suggestion_stats (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          uuid NOT NULL REFERENCES rag_service.tenants (tenant_id) ON DELETE CASCADE,
  document_group_id  uuid NOT NULL,
  click_count        integer NOT NULL DEFAULT 0,
  create_at          timestamp NOT NULL DEFAULT now(),
  update_at          timestamp NOT NULL DEFAULT now(),
  CONSTRAINT faq_suggestion_stats_click_count_chk CHECK (click_count >= 0),
  CONSTRAINT faq_suggestion_stats_tenant_group_uk UNIQUE (tenant_id, document_group_id)
);

COMMENT ON TABLE rag_service.faq_suggestion_stats IS 'Portal FAQ 推荐热度（按 document_group_id）';
COMMENT ON COLUMN rag_service.faq_suggestion_stats.tenant_id IS '所属租户';
COMMENT ON COLUMN rag_service.faq_suggestion_stats.document_group_id IS '文档组 id（与 documents.doc_group_id 对齐）';
COMMENT ON COLUMN rag_service.faq_suggestion_stats.click_count IS '推荐条点击次数';
COMMENT ON COLUMN rag_service.faq_suggestion_stats.create_at IS '创建时间；应用层禁止改写';
COMMENT ON COLUMN rag_service.faq_suggestion_stats.update_at IS '最后修改时间；由 trigger 维护';

CREATE INDEX faq_suggestion_stats_tenant_click_idx
  ON rag_service.faq_suggestion_stats (tenant_id, click_count DESC);

CREATE TRIGGER tr_faq_suggestion_stats_lmt
  BEFORE UPDATE ON rag_service.faq_suggestion_stats
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();
"""
    )


def downgrade() -> None:
    op.execute(
        """
DROP TRIGGER IF EXISTS tr_faq_suggestion_stats_lmt ON rag_service.faq_suggestion_stats;
DROP TABLE IF EXISTS rag_service.faq_suggestion_stats;
"""
    )
