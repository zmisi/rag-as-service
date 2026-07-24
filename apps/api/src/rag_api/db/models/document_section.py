from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from rag_api.db.models.base import RAG_SCHEMA, Base, TimestampMixin

if TYPE_CHECKING:
    from rag_api.db.models.document import Document
    from rag_api.db.models.document_chunk import DocumentChunk


class DocumentSection(TimestampMixin, Base):
    """H1–H6 section with full text + path (F04 / F07)."""

    __tablename__ = "document_sections"

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
    parent_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.document_sections.id", ondelete="CASCADE"),
        nullable=True,
    )
    level: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    section_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    document: Mapped[Document] = relationship(back_populates="sections")
    chunks: Mapped[list[DocumentChunk]] = relationship(back_populates="section")
