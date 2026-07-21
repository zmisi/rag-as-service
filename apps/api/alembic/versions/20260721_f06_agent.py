"""F06 agent_runs / agent_run_steps; messages.agent_run_id + summary role.

Revision ID: 20260721_f06
Revises: 20260720_f05
Create Date: 2026-07-21

Source: docs/specs/phase1/features/F06-rag-agent.md
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260721_f06"
down_revision: Union[str, Sequence[str], None] = "20260720_f05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
CREATE TABLE rag_service.agent_runs (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL REFERENCES rag_service.tenants (id) ON DELETE CASCADE,
  conversation_id  uuid NOT NULL REFERENCES rag_service.conversations (id) ON DELETE CASCADE,
  user_message_id  uuid REFERENCES rag_service.messages (id) ON DELETE SET NULL,
  used_search      boolean NOT NULL DEFAULT false,
  status           text NOT NULL,
  step_count       int NOT NULL DEFAULT 0,
  error            text,
  create_at        timestamp NOT NULL DEFAULT now(),
  update_at        timestamp NOT NULL DEFAULT now(),
  CONSTRAINT agent_runs_status_chk
    CHECK (status IN ('running', 'completed', 'truncated', 'error'))
);

COMMENT ON TABLE rag_service.agent_runs IS
  '一次用户提问触发的 Agent 执行记录；无前置意图分类';
COMMENT ON COLUMN rag_service.agent_runs.used_search IS
  '本轮是否至少执行过一次 search_knowledge';
COMMENT ON COLUMN rag_service.agent_runs.status IS
  'running/completed/truncated/error';
COMMENT ON COLUMN rag_service.agent_runs.step_count IS
  '已执行模型步数（≤ MAX_STEPS）';
COMMENT ON COLUMN rag_service.agent_runs.create_at IS '开始时间；应用层禁止改写';
COMMENT ON COLUMN rag_service.agent_runs.update_at IS '结束/更新时间；由 trigger 维护';

CREATE INDEX agent_runs_tenant_conversation_create_at_idx
  ON rag_service.agent_runs (tenant_id, conversation_id, create_at DESC);

CREATE TRIGGER tr_agent_runs_lmt
  BEFORE UPDATE ON rag_service.agent_runs
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();

CREATE TABLE rag_service.agent_run_steps (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES rag_service.tenants (id) ON DELETE CASCADE,
  agent_run_id  uuid NOT NULL REFERENCES rag_service.agent_runs (id) ON DELETE CASCADE,
  step_index    int NOT NULL,
  step_type     text NOT NULL,
  tool_name     text,
  payload       jsonb NOT NULL DEFAULT '{}',
  create_at     timestamp NOT NULL DEFAULT now(),
  update_at     timestamp NOT NULL DEFAULT now(),
  CONSTRAINT agent_run_steps_run_index_key UNIQUE (agent_run_id, step_index),
  CONSTRAINT agent_run_steps_type_chk
    CHECK (step_type IN ('llm', 'tool_call', 'tool_result', 'final'))
);

COMMENT ON TABLE rag_service.agent_run_steps IS
  'Agent Loop 逐步轨迹（模型输出 / tool_call / tool_result / final）';
COMMENT ON COLUMN rag_service.agent_run_steps.tool_name IS
  '工具名；Phase 1 仅允许 search_knowledge';
COMMENT ON COLUMN rag_service.agent_run_steps.create_at IS '步骤时间；应用层禁止改写';
COMMENT ON COLUMN rag_service.agent_run_steps.update_at IS '最后修改时间；由 trigger 维护';

CREATE INDEX agent_run_steps_run_index_idx
  ON rag_service.agent_run_steps (agent_run_id, step_index);

CREATE TRIGGER tr_agent_run_steps_lmt
  BEFORE UPDATE ON rag_service.agent_run_steps
  FOR EACH ROW
  EXECUTE FUNCTION rag_service.f_common_update_at();

ALTER TABLE rag_service.messages
  DROP CONSTRAINT messages_role_chk;

ALTER TABLE rag_service.messages
  ADD CONSTRAINT messages_role_chk
  CHECK (role IN ('user', 'assistant', 'system', 'tool', 'summary'));

ALTER TABLE rag_service.messages
  ADD COLUMN agent_run_id uuid REFERENCES rag_service.agent_runs (id) ON DELETE SET NULL;

COMMENT ON COLUMN rag_service.messages.agent_run_id IS
  '关联的 Agent 运行（assistant/tool 可选填）';
"""
    )


def downgrade() -> None:
    op.execute(
        """
ALTER TABLE rag_service.messages DROP COLUMN IF EXISTS agent_run_id;

ALTER TABLE rag_service.messages DROP CONSTRAINT IF EXISTS messages_role_chk;
ALTER TABLE rag_service.messages
  ADD CONSTRAINT messages_role_chk
  CHECK (role IN ('user', 'assistant', 'system', 'tool'));

DROP TABLE IF EXISTS rag_service.agent_run_steps;
DROP TABLE IF EXISTS rag_service.agent_runs;
"""
    )
