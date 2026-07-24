from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from rag_api.db.models.base import RAG_SCHEMA, Base, TimestampMixin

if TYPE_CHECKING:
    from rag_api.db.models.document_chunk import DocumentChunk
    from rag_api.db.models.document_file import DocumentFile
    from rag_api.db.models.document_section import DocumentSection
    from rag_api.db.models.index_job import IndexJob


class Document(TimestampMixin, Base):
    """One row = one document version (F07 / F08)."""

    __tablename__ = "documents"

    doc_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    doc_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    doc_tag: Mapped[str] = mapped_column(Text, nullable=False, default="")
    doc_group_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    content_sha256: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    publish_status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    index_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    source_modified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    embedding_provider: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_dimension: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    doc_size: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0"), default=0
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    files: Mapped[list[DocumentFile]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    index_jobs: Mapped[list[IndexJob]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    sections: Mapped[list[DocumentSection]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
