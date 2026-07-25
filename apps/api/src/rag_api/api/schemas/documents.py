"""Pydantic schemas for F03 / F07 documents."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from rag_api.db.models import Document, IngestJob


class DocumentSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    document_group_id: UUID
    title: str
    tag: str
    status: str  # alias of publish_status (API transition)
    publish_status: str
    ingest_status: str
    version: int
    is_latest: bool
    create_at: datetime
    update_at: datetime


class DocumentDetailOut(DocumentSummaryOut):
    file_name: str | None = None
    file_content_type: str | None = None
    file_size_bytes: int = 0
    file_storage_path: str | None = None
    file_metadata: dict | None = None
    file_modified_at: datetime | None = None
    warning_code: str | None = None
    warning: str | None = None


class DocumentSaveRequest(BaseModel):
    title: str | None = None
    tag: str | None = None


class IngestJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    error: str | None = None
    warning_code: str | None = None
    warning: str | None = None
    attempt_count: int
    create_at: datetime
    update_at: datetime


def document_to_summary(doc: Document) -> DocumentSummaryOut:
    return DocumentSummaryOut(
        id=doc.doc_id,
        tenant_id=doc.tenant_id,
        document_group_id=doc.doc_group_id,
        title=doc.doc_name,
        tag=doc.doc_tag,
        status=doc.publish_status,
        publish_status=doc.publish_status,
        ingest_status=doc.ingest_status,
        version=doc.version_number,
        is_latest=doc.is_latest,
        create_at=doc.create_at,
        update_at=doc.update_at,
    )


def document_to_detail(
    doc: Document,
    *,
    warning_code: str | None = None,
    warning: str | None = None,
) -> DocumentDetailOut:
    base = document_to_summary(doc)
    return DocumentDetailOut(
        **base.model_dump(),
        file_name=doc.file_name,
        file_content_type=doc.file_content_type,
        file_size_bytes=int(doc.file_size_bytes or 0),
        file_storage_path=doc.file_storage_path,
        file_metadata=dict(doc.file_metadata or {}) if doc.file_metadata else None,
        file_modified_at=doc.file_modified_at,
        warning_code=warning_code,
        warning=warning,
    )


def ingest_job_to_out(job: IngestJob) -> IngestJobOut:
    return IngestJobOut(
        status=job.status,
        error=job.error,
        warning_code=None,
        warning=None,
        attempt_count=job.attempt_count,
        create_at=job.create_at,
        update_at=job.update_at,
    )
