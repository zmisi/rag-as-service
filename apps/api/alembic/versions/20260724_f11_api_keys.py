"""F11 api_keys + api_key-owned conversations.

Revision ID: 20260724_f11_api_keys
Revises: 20260724_f12_widget_site_key
Create Date: 2026-07-24

Source: docs/specs/phase2/features/F11-tenant-public-api.md
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260724_f11_api_keys"
down_revision: Union[str, Sequence[str], None] = "20260724_f12_widget_site_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE rag_service.api_keys (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          uuid NOT NULL REFERENCES rag_service.tenants (tenant_id) ON DELETE CASCADE,
  name               text,
  key_prefix         text NOT NULL,
  key_hash           text NOT NULL,
  status             text NOT NULL DEFAULT 'active',
  last_used_at       timestamp,
  create_at          timestamp NOT NULL DEFAULT now(),
  update_at          timestamp NOT NULL DEFAULT now(),
  CONSTRAINT api_keys_key_hash_uk UNIQUE (key_hash),
  CONSTRAINT api_keys_status_chk CHECK (status IN ('active', 'revoked')),
  CONSTRAINT api_keys_prefix_chk CHECK (key_prefix LIKE 'rk_live_%')
);

COMMENT ON TABLE rag_service.api_keys IS 'F11 租户对外 API Key；仅存 hash，明文仅创建时返回一次';
COMMENT ON COLUMN rag_service.api_keys.tenant_id IS '所属租户';
COMMENT ON COLUMN rag_service.api_keys.name IS '可选显示名';
COMMENT ON COLUMN rag_service.api_keys.key_prefix IS 'rk_live_ + 其后 8 字符掩码';
COMMENT ON COLUMN rag_service.api_keys.key_hash IS '完整 secret 的不可逆哈希；禁止存明文';
COMMENT ON COLUMN rag_service.api_keys.status IS 'active | revoked';
COMMENT ON COLUMN rag_service.api_keys.last_used_at IS '最近成功鉴权使用时间（可选审计）';
COMMENT ON COLUMN rag_service.api_keys.create_at IS '创建时间；应用层禁止改写';
COMMENT ON COLUMN rag_service.api_keys.update_at IS '最后修改时间；由 trigger 维护';

CREATE INDEX api_keys_tenant_idx
  ON rag_service.api_keys (tenant_id);

CREATE TRIGGER tr_api_keys_lmt
  BEFORE UPDATE ON rag_service.api_keys
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();

ALTER TABLE rag_service.conversations
  DROP CONSTRAINT IF EXISTS conversations_owner_xor_chk;

ALTER TABLE rag_service.conversations
  ADD COLUMN api_key_id uuid REFERENCES rag_service.api_keys (id) ON DELETE CASCADE;

ALTER TABLE rag_service.conversations
  ADD CONSTRAINT conversations_owner_xor_chk
  CHECK (
    (
      (user_id IS NOT NULL)::int
      + (site_key_id IS NOT NULL)::int
      + (api_key_id IS NOT NULL)::int
    ) = 1
  );

COMMENT ON COLUMN rag_service.conversations.api_key_id IS 'F11 对外 API 会话归属；与 user_id / site_key_id 互斥';
"""
    )


def downgrade() -> None:
    op.execute(
        """
ALTER TABLE rag_service.conversations
  DROP CONSTRAINT IF EXISTS conversations_owner_xor_chk;

DELETE FROM rag_service.conversations WHERE api_key_id IS NOT NULL;

ALTER TABLE rag_service.conversations
  DROP COLUMN IF EXISTS api_key_id;

ALTER TABLE rag_service.conversations
  ADD CONSTRAINT conversations_owner_xor_chk
  CHECK (
    (user_id IS NOT NULL AND site_key_id IS NULL)
    OR (user_id IS NULL AND site_key_id IS NOT NULL)
  );

DROP TRIGGER IF EXISTS tr_api_keys_lmt ON rag_service.api_keys;
DROP TABLE IF EXISTS rag_service.api_keys;
"""
    )
