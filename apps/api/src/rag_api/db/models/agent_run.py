from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rag_api.db.models.base import RAG_SCHEMA, Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from rag_api.db.models.agent_run_step import AgentRunStep
    from rag_api.db.models.conversation import Conversation
    from rag_api.db.models.message import Message


class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_message_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    used_search: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    step_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    conversation: Mapped[Conversation] = relationship()
    user_message: Mapped[Optional[Message]] = relationship(
        foreign_keys=[user_message_id],
    )
    steps: Mapped[list[AgentRunStep]] = relationship(
        back_populates="agent_run",
        order_by="AgentRunStep.step_index",
    )
