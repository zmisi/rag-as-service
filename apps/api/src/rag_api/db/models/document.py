from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rag_api.db.models.base import RAG_SCHEMA, Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from rag_api.db.models.document_file import DocumentFile
    from rag_api.db.models.index_job import IndexJob


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tag: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    version: Mapped[str] = mapped_column(Text, nullable=False, default="0.0")
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.users.id", ondelete="RESTRICT"),
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
