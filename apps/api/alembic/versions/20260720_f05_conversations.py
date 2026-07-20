"""F05 conversations / messages schema.

Revision ID: 20260720_f05
Revises: 20260720_f01
Create Date: 2026-07-20

Source: docs/specs/phase1/features/F05-conversations.md
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260720_f05"
down_revision: Union[str, Sequence[str], None] = "20260720_f01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE rag_service.conversations (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id  uuid NOT NULL REFERENCES rag_service.tenants (id) ON DELETE CASCADE,
  user_id    uuid NOT NULL REFERENCES rag_service.users (id) ON DELETE CASCADE,
  title      text NOT NULL DEFAULT '新会话',
  status     text NOT NULL DEFAULT 'active',
  deleted_at timestamp,
  create_at  timestamp NOT NULL DEFAULT now(),
  update_at  timestamp NOT NULL DEFAULT now(),
  CONSTRAINT conversations_status_chk CHECK (status IN ('active', 'archived'))
);

COMMENT ON TABLE rag_service.conversations IS '租户成员聊天会话；软删除用 deleted_at';
COMMENT ON COLUMN rag_service.conversations.id IS '会话主键';
COMMENT ON COLUMN rag_service.conversations.tenant_id IS '所属租户';
COMMENT ON COLUMN rag_service.conversations.user_id IS '创建者用户';
COMMENT ON COLUMN rag_service.conversations.title IS '会话标题；默认「新会话」';
COMMENT ON COLUMN rag_service.conversations.status IS 'active 或 archived';
COMMENT ON COLUMN rag_service.conversations.deleted_at IS '软删除时间；非空则列表不可见';
COMMENT ON COLUMN rag_service.conversations.create_at IS '创建时间；应用层禁止改写';
COMMENT ON COLUMN rag_service.conversations.update_at IS '最后修改时间；由 trigger 维护';

CREATE INDEX conversations_tenant_user_status_idx
  ON rag_service.conversations (tenant_id, user_id, status)
  WHERE deleted_at IS NULL;

CREATE TRIGGER tr_conversations_lmt
  BEFORE UPDATE ON rag_service.conversations
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();

CREATE TABLE rag_service.messages (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES rag_service.conversations (id) ON DELETE CASCADE,
  tenant_id       uuid NOT NULL REFERENCES rag_service.tenants (id) ON DELETE CASCADE,
  role            text NOT NULL,
  content         text NOT NULL,
  meta            jsonb,
  create_at       timestamp NOT NULL DEFAULT now(),
  update_at       timestamp NOT NULL DEFAULT now(),
  CONSTRAINT messages_role_chk CHECK (role IN ('user', 'assistant', 'system', 'tool'))
);

COMMENT ON TABLE rag_service.messages IS '会话消息；role 含 user/assistant/system/tool';
COMMENT ON COLUMN rag_service.messages.id IS '消息主键';
COMMENT ON COLUMN rag_service.messages.conversation_id IS '所属会话';
COMMENT ON COLUMN rag_service.messages.tenant_id IS '所属租户（强制隔离）';
COMMENT ON COLUMN rag_service.messages.role IS '消息角色';
COMMENT ON COLUMN rag_service.messages.content IS '消息正文';
COMMENT ON COLUMN rag_service.messages.meta IS '扩展 JSON（F06 tool 轨迹等）';
COMMENT ON COLUMN rag_service.messages.create_at IS '创建时间；应用层禁止改写';
COMMENT ON COLUMN rag_service.messages.update_at IS '最后修改时间；由 trigger 维护';

CREATE INDEX messages_conversation_create_at_idx
  ON rag_service.messages (conversation_id, create_at);

CREATE TRIGGER tr_messages_lmt
  BEFORE UPDATE ON rag_service.messages
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();
"""
    )


def downgrade() -> None:
    op.execute(
        """
DROP TABLE IF EXISTS rag_service.messages;
DROP TABLE IF EXISTS rag_service.conversations;
"""
    )
