"""F06 turn orchestration: persist user → AgentLoop → persist assistant + agent_run."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from rag_api.agent.loop import AgentLoop, LoopResult
from rag_api.clients.llm import LlmClient
from rag_api.db.models import AgentRun, AgentRunStep, Message
from rag_api.indexing.search import KnowledgeSearcher
from rag_api.observability.timing import StageTimer
from rag_api.services import conversations as conv_svc


@dataclass
class TurnResult:
    user: Message
    assistant: Message
    agent_run: AgentRun
    loop: LoopResult
    conversation_title: str | None = None
    server_ms: float = 0.0


def run_user_turn(
    db: Session,
    *,
    conversation_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    content: str,
    llm: LlmClient,
    searcher: KnowledgeSearcher,
) -> TurnResult:
    """Persist user message, run Agent Loop, persist assistant + traces."""
    timer = StageTimer(
        "turn",
        conversation_id=str(conversation_id),
        tenant_id=str(tenant_id),
        content_chars=len(content),
    )

    # Ownership + active check (raises 404/409)
    user_msg = conv_svc.add_message(
        db,
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        role="user",
        content=content,
        meta=None,
    )
    auto_title = conv_svc.maybe_set_title_from_first_message(
        db,
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        user_content=content,
    )
    timer.mark("persist_user")

    agent_run = AgentRun(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        user_message_id=user_msg.id,
        used_search=False,
        status="running",
        step_count=0,
    )
    db.add(agent_run)
    db.commit()
    db.refresh(agent_run)
    timer.mark("create_agent_run", agent_run_id=str(agent_run.id))

    history = conv_svc.list_messages(
        db,
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    timer.mark("load_history", history_count=len(history))

    loop = AgentLoop(llm=llm, searcher=searcher, tenant_id=tenant_id)
    result = loop.run(history=history, user_content=content)
    timer.mark(
        "agent_loop",
        status=result.status,
        steps=result.step_count,
        used_search=result.used_search,
    )

    for i, step in enumerate(result.steps, start=1):
        db.add(
            AgentRunStep(
                tenant_id=tenant_id,
                agent_run_id=agent_run.id,
                step_index=i,
                step_type=step.step_type,
                tool_name=step.tool_name,
                payload=step.payload or {},
            )
        )

    agent_run.used_search = result.used_search
    agent_run.status = result.status
    agent_run.step_count = result.step_count
    agent_run.error = result.error

    assistant = Message(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        role="assistant",
        content=result.reply,
        meta={"agent_run_id": str(agent_run.id), "used_search": result.used_search},
        agent_run_id=agent_run.id,
    )
    db.add(assistant)
    db.commit()
    db.refresh(assistant)
    db.refresh(agent_run)
    timer.mark("persist_assistant", reply_chars=len(result.reply or ""))

    total_ms = timer.finish(
        status=result.status,
        used_search=result.used_search,
        step_count=result.step_count,
    )

    return TurnResult(
        user=user_msg,
        assistant=assistant,
        agent_run=agent_run,
        loop=result,
        conversation_title=auto_title,
        server_ms=total_ms,
    )
