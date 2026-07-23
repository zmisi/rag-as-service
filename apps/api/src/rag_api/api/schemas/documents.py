"""Pydantic schemas for F03 / F07 documents."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from rag_api.db.models import Document, DocumentFile


class DocumentFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    version: int
    create_at: datetime
    update_at: datetime


class DocumentSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    document_group_id: UUID
    title: str
    tag: str
    status: str  # alias of publish_status (API transition)
    publish_status: str
    index_status: str
    version: int
    is_latest: bool
    create_at: datetime
    update_at: datetime


class DocumentDetailOut(DocumentSummaryOut):
    files: list[DocumentFileOut] = Field(default_factory=list)


class DocumentSaveRequest(BaseModel):
    title: str | None = None
    tag: str | None = None


class IndexJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    error: str | None = None
    attempt_count: int
    create_at: datetime
    update_at: datetime


def file_to_out(f: DocumentFile) -> DocumentFileOut:
    return DocumentFileOut.model_validate(f)


def document_to_summary(doc: Document) -> DocumentSummaryOut:
    return DocumentSummaryOut(
        id=doc.id,
        tenant_id=doc.tenant_id,
        document_group_id=doc.document_group_id,
        title=doc.title,
        tag=doc.tag,
        status=doc.publish_status,
        publish_status=doc.publish_status,
        index_status=doc.index_status,
        version=doc.version,
        is_latest=doc.is_latest,
        create_at=doc.create_at,
        update_at=doc.update_at,
    )


def document_to_detail(doc: Document) -> DocumentDetailOut:
    base = document_to_summary(doc)
    return DocumentDetailOut(
        **base.model_dump(),
        files=[file_to_out(f) for f in (doc.files or [])],
    )
