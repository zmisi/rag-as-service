from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rag_api.db.models.base import RAG_SCHEMA, Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from rag_api.db.models.conversation import Conversation


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    agent_run_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.agent_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
