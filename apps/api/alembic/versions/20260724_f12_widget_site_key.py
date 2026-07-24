"""F12 widget_site_keys + widget-owned conversations.

Revision ID: 20260724_f12_widget_site_key
Revises: 20260724_f13_is_hot
Create Date: 2026-07-24

Source: docs/specs/phase2/features/F12-embed-widget.md
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260724_f12_widget_site_key"
down_revision: Union[str, Sequence[str], None] = "20260724_f13_is_hot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE rag_service.widget_site_keys (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          uuid NOT NULL REFERENCES rag_service.tenants (tenant_id) ON DELETE CASCADE,
  public_key         text NOT NULL,
  status             text NOT NULL DEFAULT 'active',
  allowed_origins    text[] NOT NULL DEFAULT '{}',
  name               text,
  create_at          timestamp NOT NULL DEFAULT now(),
  update_at          timestamp NOT NULL DEFAULT now(),
  CONSTRAINT widget_site_keys_public_key_uk UNIQUE (public_key),
  CONSTRAINT widget_site_keys_status_chk CHECK (status IN ('active', 'revoked')),
  CONSTRAINT widget_site_keys_public_key_prefix_chk CHECK (public_key LIKE 'pk_%')
);

COMMENT ON TABLE rag_service.widget_site_keys IS 'F12 Embed Widget 公开 site key + Origin 白名单';
COMMENT ON COLUMN rag_service.widget_site_keys.tenant_id IS '所属租户';
COMMENT ON COLUMN rag_service.widget_site_keys.public_key IS '公开 pk_… key；可出现在前端';
COMMENT ON COLUMN rag_service.widget_site_keys.status IS 'active | revoked';
COMMENT ON COLUMN rag_service.widget_site_keys.allowed_origins IS '精确 scheme+host 与可选端口；空则全部拒绝';
COMMENT ON COLUMN rag_service.widget_site_keys.name IS '可选显示名';
COMMENT ON COLUMN rag_service.widget_site_keys.create_at IS '创建时间；应用层禁止改写';
COMMENT ON COLUMN rag_service.widget_site_keys.update_at IS '最后修改时间；由 trigger 维护';

CREATE INDEX widget_site_keys_tenant_idx
  ON rag_service.widget_site_keys (tenant_id);

CREATE TRIGGER tr_widget_site_keys_lmt
  BEFORE UPDATE ON rag_service.widget_site_keys
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();

ALTER TABLE rag_service.conversations
  ALTER COLUMN user_id DROP NOT NULL;

ALTER TABLE rag_service.conversations
  ADD COLUMN site_key_id uuid REFERENCES rag_service.widget_site_keys (id) ON DELETE CASCADE;

ALTER TABLE rag_service.conversations
  ADD CONSTRAINT conversations_owner_xor_chk
  CHECK (
    (user_id IS NOT NULL AND site_key_id IS NULL)
    OR (user_id IS NULL AND site_key_id IS NOT NULL)
  );

COMMENT ON COLUMN rag_service.conversations.site_key_id IS 'F12 Widget 会话归属；与 user_id 互斥';
"""
    )


def downgrade() -> None:
    op.execute(
        """
ALTER TABLE rag_service.conversations
  DROP CONSTRAINT IF EXISTS conversations_owner_xor_chk;

ALTER TABLE rag_service.conversations
  DROP COLUMN IF EXISTS site_key_id;

DELETE FROM rag_service.conversations WHERE user_id IS NULL;

ALTER TABLE rag_service.conversations
  ALTER COLUMN user_id SET NOT NULL;

DROP TRIGGER IF EXISTS tr_widget_site_keys_lmt ON rag_service.widget_site_keys;
DROP TABLE IF EXISTS rag_service.widget_site_keys;
"""
    )
