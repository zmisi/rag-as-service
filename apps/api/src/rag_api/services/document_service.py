"""Document management business rules (F03 / F07)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from rag_api.config import get_settings
from rag_api.db.models import Document, DocumentFile, IndexJob
from rag_api.domain.documents.constants import (
    INDEX_JOB_ERROR_DUPLICATE_CONTENT_SHA256,
    MAX_FILE_BYTES,
    WARNING_CODE_DUPLICATE_CONTENT_SHA256,
    WARNING_DUPLICATE_CONTENT_SHA256,
    content_sha256,
    is_valid_tag,
    next_version,
)
from rag_api.domain.documents.file_type import FileTypeError, validate_file_type
from rag_api.indexing.worker import mark_document_index_not_latest, process_index_job
from rag_api.services.storage_service import StorageService


@dataclass(frozen=True)
class PublishResult:
    document: Document
    warning_code: str | None = None
    warning: str | None = None


def _get_document(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
) -> Document:
    doc = db.scalar(
        select(Document)
        .where(
            Document.doc_id == document_id,
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
    group_id = uuid4()
    doc = Document(
        tenant_id=tenant_id,
        created_by=user_id,
        doc_group_id=group_id,
        publish_status="draft",
        index_status="pending",
        version_number=1,
        is_latest=True,
        source_metadata={},
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
            Document.is_latest.is_(True),
        )
        .order_by(Document.update_at.desc())
    )
    if tag:
        if not is_valid_tag(tag):
            raise HTTPException(status_code=422, detail="Invalid tag filter")
        stmt = stmt.where(Document.doc_tag == tag)
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
    if doc.publish_status == "published":
        raise HTTPException(status_code=409, detail="Published document is read-only")
    if doc.publish_status == "review":
        doc.publish_status = "draft"

    if title is not None:
        doc.doc_name = title
    if tag is not None:
        if tag != "" and not is_valid_tag(tag):
            raise HTTPException(status_code=400, detail="Invalid tag")
        doc.doc_tag = tag

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
    try:
        validate_file_type(filename, data)
    except FileTypeError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    doc = _get_document(db, document_id=document_id, tenant_id=tenant_id)
    if doc.publish_status == "published":
        raise HTTPException(status_code=409, detail="Published document is read-only")
    if doc.publish_status == "review":
        doc.publish_status = "draft"

    work_version = int(doc.version_number)

    storage_key = storage.storage_key(
        tenant_id=tenant_id,
        document_id=document_id,
        version=str(work_version),
        filename=filename,
    )
    storage.write_bytes(storage_key, data)

    record = DocumentFile(
        tenant_id=tenant_id,
        doc_id=document_id,
        version=work_version,
        storage_key=storage_key,
        filename=filename,
        content_type=content_type or "application/octet-stream",
        size_bytes=len(data),
    )
    db.add(record)
    db.flush()
    doc.doc_size = int(
        db.scalar(
            select(func.coalesce(func.sum(DocumentFile.size_bytes), 0)).where(
                DocumentFile.doc_id == document_id,
                DocumentFile.tenant_id == tenant_id,
            )
        )
        or 0
    )
    db.commit()
    db.refresh(record)
    return record


def submit_for_review(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
) -> Document:
    doc = _get_document(db, document_id=document_id, tenant_id=tenant_id)
    if doc.publish_status != "draft":
        raise HTTPException(status_code=409, detail="Only draft documents can be submitted")

    title = (doc.doc_name or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    if not is_valid_tag(doc.doc_tag):
        raise HTTPException(status_code=400, detail="Tag is required")
    if not doc.files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    doc.publish_status = "review"
    db.commit()
    db.refresh(doc)
    return doc


def _apply_source_metadata(
    doc: Document,
    storage: StorageService,
) -> None:
    """Set content_sha256 / source_* from attached files when possible."""
    files = list(doc.files or [])
    if not files:
        return
    primary = files[0]
    hasher_parts: list[bytes] = []
    for f in sorted(files, key=lambda x: x.filename):
        try:
            hasher_parts.append(storage.read_bytes(f.storage_key))
        except FileNotFoundError:
            continue
    if hasher_parts:
        doc.content_sha256 = content_sha256(b"".join(hasher_parts))
    doc.source_uri = primary.storage_key
    ext = Path(primary.filename).suffix.lower().lstrip(".") or None
    doc.source_type = ext


def _find_ready_duplicate(
    db: Session,
    *,
    tenant_id: UUID,
    content_hash: str | None,
    exclude_id: UUID,
) -> Document | None:
    if not content_hash:
        return None
    return db.scalar(
        select(Document)
        .where(
            Document.tenant_id == tenant_id,
            Document.content_sha256 == content_hash,
            Document.index_status == "ready",
            Document.is_latest.is_(True),
            Document.deleted_at.is_(None),
            Document.doc_id != exclude_id,
        )
        .limit(1)
    )


def publish_document(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
) -> PublishResult:
    doc = _get_document(db, document_id=document_id, tenant_id=tenant_id)
    if doc.publish_status != "review":
        raise HTTPException(status_code=409, detail="Only review documents can be published")

    storage = StorageService()
    _apply_source_metadata(doc, storage)

    doc.publish_status = "published"
    doc.index_status = "pending"
    doc.error_message = None

    dup = _find_ready_duplicate(
        db,
        tenant_id=tenant_id,
        content_hash=doc.content_sha256,
        exclude_id=doc.doc_id,
    )
    if dup is not None:
        doc.index_status = "ready"
        doc.is_latest = True
        # Keep other versions in this group from being listed as latest.
        others = list(
            db.scalars(
                select(Document).where(
                    Document.tenant_id == tenant_id,
                    Document.doc_group_id == doc.doc_group_id,
                    Document.doc_id != doc.doc_id,
                )
            ).all()
        )
        for other in others:
            other.is_latest = False
        job = IndexJob(
            tenant_id=tenant_id,
            doc_id=document_id,
            version=int(doc.version_number),
            status="succeeded",
            error=INDEX_JOB_ERROR_DUPLICATE_CONTENT_SHA256,
        )
        db.add(job)
        db.commit()
        db.refresh(doc)
        return PublishResult(
            document=doc,
            warning_code=WARNING_CODE_DUPLICATE_CONTENT_SHA256,
            warning=WARNING_DUPLICATE_CONTENT_SHA256,
        )

    job = IndexJob(
        tenant_id=tenant_id,
        doc_id=document_id,
        version=int(doc.version_number),
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
    return PublishResult(document=doc)

def new_version(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
) -> Document:
    """Create a new draft version row; old latest stays searchable until reindex."""
    old = _get_document(db, document_id=document_id, tenant_id=tenant_id)
    if old.publish_status != "published":
        raise HTTPException(
            status_code=409,
            detail="Only published documents can start a new version",
        )

    max_version = db.scalar(
        select(func.max(Document.version_number)).where(
            Document.tenant_id == tenant_id,
            Document.doc_group_id == old.doc_group_id,
        )
    )
    new_ver = next_version(int(max_version or old.version_number))

    old.is_latest = False
    draft = Document(
        tenant_id=tenant_id,
        doc_group_id=old.doc_group_id,
        doc_name=old.doc_name,
        doc_tag=old.doc_tag,
        created_by=old.created_by,
        publish_status="draft",
        index_status="pending",
        version_number=new_ver,
        is_latest=True,
        source_type=old.source_type,
        source_uri=old.source_uri,
        source_metadata=dict(old.source_metadata or {}),
    )
    db.add(draft)
    db.flush()

    for f in old.files:
        db.add(
            DocumentFile(
                tenant_id=tenant_id,
                doc_id=draft.doc_id,
                version=new_ver,
                storage_key=f.storage_key,
                filename=f.filename,
                content_type=f.content_type,
                size_bytes=f.size_bytes,
            )
        )
    draft.doc_size = sum(f.size_bytes for f in old.files)

    db.commit()
    return _get_document(db, document_id=draft.doc_id, tenant_id=tenant_id)


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
            IndexJob.doc_id == document_id,
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
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    siblings = list(
        db.scalars(
            select(Document).where(
                Document.tenant_id == tenant_id,
                Document.doc_group_id == doc.doc_group_id,
                Document.deleted_at.is_(None),
            )
        ).all()
    )
    for row in siblings:
        row.deleted_at = now
        row.is_latest = False
        mark_document_index_not_latest(
            db, tenant_id=tenant_id, document_id=row.doc_id
        )
    db.commit()
    db.refresh(doc)
    return doc
