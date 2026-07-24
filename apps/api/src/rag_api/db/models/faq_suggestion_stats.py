from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from rag_api.db.models.base import RAG_SCHEMA, Base, TimestampMixin, UUIDPrimaryKeyMixin


class FaqSuggestionStats(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-tenant FAQ click heat keyed by document_group_id (F13)."""

    __tablename__ = "faq_suggestion_stats"

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    document_group_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    click_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0"), default=0
    )
