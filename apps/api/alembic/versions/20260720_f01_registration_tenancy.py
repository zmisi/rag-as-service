"""F01 registration / tenancy schema (users, tenants, tenant_members).

Revision ID: 20260720_f01
Revises:
Create Date: 2026-07-20

Source: docs/specs/phase1/features/F01-registration-tenancy-data-model.md
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260720_f01"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
CREATE SCHEMA IF NOT EXISTS rag_service;

CREATE OR REPLACE FUNCTION rag_service.f_common_update_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.update_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION rag_service.f_common_update_at() IS
  'BEFORE UPDATE：仅刷新 update_at，不修改 create_at';

CREATE TABLE rag_service.users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email         text NOT NULL,
  password_hash text NOT NULL,
  create_at     timestamp NOT NULL DEFAULT now(),
  update_at     timestamp NOT NULL DEFAULT now(),
  CONSTRAINT users_email_key UNIQUE (email)
);

COMMENT ON TABLE rag_service.users IS '平台用户；email 全局唯一';
COMMENT ON COLUMN rag_service.users.id IS '用户主键';
COMMENT ON COLUMN rag_service.users.email IS '登录邮箱，小写存储';
COMMENT ON COLUMN rag_service.users.password_hash IS '不可逆密码哈希';
COMMENT ON COLUMN rag_service.users.create_at IS '创建时间；应用层禁止改写';
COMMENT ON COLUMN rag_service.users.update_at IS '最后修改时间；由 trigger 维护';

CREATE TRIGGER tr_users_lmt
  BEFORE UPDATE ON rag_service.users
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();

CREATE TABLE rag_service.tenants (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subdomain    text NOT NULL,
  display_name text,
  create_at    timestamp NOT NULL DEFAULT now(),
  update_at    timestamp NOT NULL DEFAULT now(),
  CONSTRAINT tenants_subdomain_key UNIQUE (subdomain),
  CONSTRAINT tenants_subdomain_length_chk CHECK (char_length(subdomain) BETWEEN 3 AND 32),
  CONSTRAINT tenants_subdomain_format_chk CHECK (subdomain ~ '^[a-z0-9]([a-z0-9-]*[a-z0-9])?$')
);

COMMENT ON TABLE rag_service.tenants IS '租户；subdomain 对应子域 Host';
COMMENT ON COLUMN rag_service.tenants.id IS '租户主键；全库隔离键';
COMMENT ON COLUMN rag_service.tenants.subdomain IS '子域标识，全局唯一，Phase1 注册后不可改';
COMMENT ON COLUMN rag_service.tenants.display_name IS '展示名（可选）';
COMMENT ON COLUMN rag_service.tenants.create_at IS '创建时间；应用层禁止改写';
COMMENT ON COLUMN rag_service.tenants.update_at IS '最后修改时间；由 trigger 维护';

CREATE TRIGGER tr_tenants_lmt
  BEFORE UPDATE ON rag_service.tenants
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();

CREATE TABLE rag_service.tenant_members (
  id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES rag_service.tenants (id) ON DELETE CASCADE,
  user_id   uuid NOT NULL REFERENCES rag_service.users (id) ON DELETE CASCADE,
  role      text NOT NULL,
  create_at timestamp NOT NULL DEFAULT now(),
  update_at timestamp NOT NULL DEFAULT now(),
  CONSTRAINT tenant_members_tenant_user_key UNIQUE (tenant_id, user_id),
  CONSTRAINT tenant_members_role_chk CHECK (role IN ('owner'))
);

COMMENT ON TABLE rag_service.tenant_members IS '用户与租户成员关系';
COMMENT ON COLUMN rag_service.tenant_members.id IS '成员关系主键';
COMMENT ON COLUMN rag_service.tenant_members.tenant_id IS '所属租户';
COMMENT ON COLUMN rag_service.tenant_members.user_id IS '成员用户';
COMMENT ON COLUMN rag_service.tenant_members.role IS 'Phase1 注册为 owner';
COMMENT ON COLUMN rag_service.tenant_members.create_at IS '加入时间；应用层禁止改写';
COMMENT ON COLUMN rag_service.tenant_members.update_at IS '最后修改时间；由 trigger 维护';

CREATE INDEX tenant_members_user_id_idx ON rag_service.tenant_members (user_id);
CREATE INDEX tenant_members_tenant_id_idx ON rag_service.tenant_members (tenant_id);

CREATE TRIGGER tr_tenant_members_lmt
  BEFORE UPDATE ON rag_service.tenant_members
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();
"""
    )


def downgrade() -> None:
    op.execute(
        """
DROP TABLE IF EXISTS rag_service.tenant_members;
DROP TABLE IF EXISTS rag_service.tenants;
DROP TABLE IF EXISTS rag_service.users;
DROP FUNCTION IF EXISTS rag_service.f_common_update_at();
"""
    )
