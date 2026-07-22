"""Document management business rules (F03)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from rag_api.db.models import Document, DocumentFile, IndexJob
from rag_api.domain.documents.constants import (
    MAX_FILE_BYTES,
    bump_version,
    file_type_reject_message,
    is_allowed_extension,
    is_valid_tag,
)
from rag_api.config import get_settings
from rag_api.indexing.worker import deactivate_document_chunks, process_index_job
from rag_api.services.storage_service import StorageService


def _get_document(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
) -> Document:
    doc = db.scalar(
        select(Document)
        .where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
            Document.deleted_at.is_(None),
        )
        .options(selectinload(Document.files))
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def create_document(
    db: Session,
    *,
    tenant_id: UUID,
    user_id: UUID,
) -> Document:
    doc = Document(
        tenant_id=tenant_id,
        created_by=user_id,
        status="draft",
        version="0.0",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def list_documents(
    db: Session,
    *,
    tenant_id: UUID,
    tag: str | None = None,
) -> list[Document]:
    stmt = (
        select(Document)
        .where(
            Document.tenant_id == tenant_id,
            Document.deleted_at.is_(None),
        )
        .order_by(Document.update_at.desc())
    )
    if tag:
        if not is_valid_tag(tag):
            raise HTTPException(status_code=422, detail="Invalid tag filter")
        stmt = stmt.where(Document.tag == tag)
    return list(db.scalars(stmt).all())


def get_document_detail(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
) -> Document:
    return _get_document(db, document_id=document_id, tenant_id=tenant_id)


def save_draft(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
    title: str | None = None,
    tag: str | None = None,
) -> Document:
    doc = _get_document(db, document_id=document_id, tenant_id=tenant_id)
    if doc.status == "published":
        raise HTTPException(status_code=409, detail="Published document is read-only")
    if doc.status == "review":
        doc.status = "draft"

    if title is not None:
        doc.title = title
    if tag is not None:
        if tag != "" and not is_valid_tag(tag):
            raise HTTPException(status_code=400, detail="Invalid tag")
        doc.tag = tag

    db.commit()
    db.refresh(doc)
    return doc


def add_file(
    db: Session,
    storage: StorageService,
    *,
    document_id: UUID,
    tenant_id: UUID,
    filename: str,
    content_type: str,
    data: bytes,
) -> DocumentFile:
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 20MB limit")
    if not is_allowed_extension(filename):
        raise HTTPException(
            status_code=400,
            detail=file_type_reject_message(filename),
        )

    doc = _get_document(db, document_id=document_id, tenant_id=tenant_id)
    if doc.status == "published":
        raise HTTPException(status_code=409, detail="Published document is read-only")
    if doc.status == "review":
        doc.status = "draft"

    work_version = doc.version

    storage_key = storage.storage_key(
        tenant_id=tenant_id,
        document_id=document_id,
        version=work_version,
        filename=filename,
    )
    storage.write_bytes(storage_key, data)

    record = DocumentFile(
        tenant_id=tenant_id,
        document_id=document_id,
        version=work_version,
        storage_key=storage_key,
        filename=filename,
        content_type=content_type or "application/octet-stream",
        size_bytes=len(data),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _draft_files(doc: Document) -> list[DocumentFile]:
    if doc.version == "0.0":
        return [f for f in doc.files if f.version == "0.0"]
    return list(doc.files)


def submit_for_review(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
) -> Document:
    doc = _get_document(db, document_id=document_id, tenant_id=tenant_id)
    if doc.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft documents can be submitted")

    title = (doc.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    if not is_valid_tag(doc.tag):
        raise HTTPException(status_code=400, detail="Tag is required")
    files = _draft_files(doc)
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    doc.status = "review"
    db.commit()
    db.refresh(doc)
    return doc


def publish_document(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
) -> Document:
    doc = _get_document(db, document_id=document_id, tenant_id=tenant_id)
    if doc.status != "review":
        raise HTTPException(status_code=409, detail="Only review documents can be published")

    new_version = bump_version(doc.version)
    doc.version = new_version
    doc.status = "published"

    for f in doc.files:
        f.version = new_version

    job = IndexJob(
        tenant_id=tenant_id,
        document_id=document_id,
        version=new_version,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(doc)
    db.refresh(job)

    settings = get_settings()
    if settings.index_sync_on_publish:
        try:
            process_index_job(db, job.id)
        except Exception:  # noqa: BLE001 — publish already committed; job may be failed
            pass
        db.refresh(doc)
    return doc


def new_version(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
) -> Document:
    doc = _get_document(db, document_id=document_id, tenant_id=tenant_id)
    if doc.status != "published":
        raise HTTPException(status_code=409, detail="Only published documents can start a new version")
    doc.status = "draft"
    db.commit()
    db.refresh(doc)
    return doc


def latest_index_job(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
) -> IndexJob | None:
    _get_document(db, document_id=document_id, tenant_id=tenant_id)
    return db.scalar(
        select(IndexJob)
        .where(
            IndexJob.document_id == document_id,
            IndexJob.tenant_id == tenant_id,
        )
        .order_by(IndexJob.create_at.desc())
        .limit(1)
    )


def soft_delete_document(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
) -> Document:
    from datetime import datetime, timezone

    doc = _get_document(db, document_id=document_id, tenant_id=tenant_id)
    doc.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    deactivate_document_chunks(db, tenant_id=tenant_id, document_id=document_id)
    db.commit()
    db.refresh(doc)
    return doc
