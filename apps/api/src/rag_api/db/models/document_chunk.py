from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from rag_api.db.models.base import RAG_SCHEMA, Base, TimestampMixin

if TYPE_CHECKING:
    from rag_api.db.models.document import Document
    from rag_api.db.models.document_section import DocumentSection


class DocumentChunk(TimestampMixin, Base):
    """Leaf chunk metadata. Embeddings are written/read via raw SQL (pgvector)."""

    __tablename__ = "document_chunks"

    chunk_id: Mapped[UUID] = mapped_column(
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
    section_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.document_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    chunk_type: Mapped[str] = mapped_column(Text, nullable=False, default="text")
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # content_tsv is tsvector — managed via raw SQL; not mapped for ORM writes.
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata_",
        JSONB,
        nullable=True,
        default=dict,
    )
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    document: Mapped[Document] = relationship(back_populates="chunks")
    section: Mapped[DocumentSection] = relationship(back_populates="chunks")
