from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from rag_api.db.models.base import RAG_SCHEMA, Base, TimestampMixin

if TYPE_CHECKING:
    from rag_api.db.models.document import Document


class IndexJob(TimestampMixin, Base):
    __tablename__ = "index_jobs"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    doc_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.documents.doc_id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    document: Mapped[Document] = relationship(back_populates="index_jobs")
