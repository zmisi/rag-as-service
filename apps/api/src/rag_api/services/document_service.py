"""Document management business rules (F03 / F07)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rag_api.config import get_settings
from rag_api.db.models import Document, IngestJob
from rag_api.domain.documents.constants import (
    MAX_FILE_BYTES,
    content_sha256,
    duplicate_content_conflict_detail,
    is_valid_tag,
    next_version,
)
from rag_api.domain.documents.file_type import FileTypeError, validate_file_type
from rag_api.ingestion.file_metadata import (
    apply_modified_at_from_metadata,
    build_upload_metadata,
)
from rag_api.ingestion.worker import mark_document_ingest_not_latest, process_ingest_job
from rag_api.services.storage_service import StorageService


@dataclass(frozen=True)
class PublishResult:
    """Published document plus optional duplicate-content warning fields."""

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
        select(Document).where(
            Document.doc_id == document_id,
            Document.tenant_id == tenant_id,
            Document.deleted_at.is_(None),
        )
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
    """Create an empty draft document v1 in a new ``doc_group``."""
    group_id = uuid4()
    doc = Document(
        tenant_id=tenant_id,
        created_by=user_id,
        doc_group_id=group_id,
        publish_status="draft",
        ingest_status="pending",
        version_number=1,
        is_latest=True,
        file_metadata={},
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
    """List latest non-deleted documents for the tenant, optionally by tag."""
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
    """Load a tenant document by id; 404 if missing or soft-deleted."""
    return _get_document(db, document_id=document_id, tenant_id=tenant_id)


def save_draft(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
    title: str | None = None,
    tag: str | None = None,
) -> Document:
    """Update draft/review title and tag; rejects published documents."""
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
) -> Document:
    """Attach or replace the single source file on this document version."""
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
    if doc.file_storage_path:
        storage.delete(doc.file_storage_path)

    storage_path = storage.storage_key(
        tenant_id=tenant_id,
        document_id=document_id,
        version=str(work_version),
        filename=filename,
    )
    storage.write_bytes(storage_path, data)

    doc.file_storage_path = storage_path
    doc.file_name = filename
    doc.file_content_type = content_type or "application/octet-stream"
    doc.file_size_bytes = len(data)
    doc.file_type = Path(filename).suffix.lower().lstrip(".") or None
    doc.file_metadata = build_upload_metadata(
        filename=filename,
        content_type=doc.file_content_type,
        size_bytes=len(data),
    )
    doc.file_modified_at = apply_modified_at_from_metadata(doc.file_metadata)

    db.commit()
    db.refresh(doc)
    return doc


def submit_for_review(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
) -> Document:
    """Validate draft fields and move document to review status."""
    doc = _get_document(db, document_id=document_id, tenant_id=tenant_id)
    if doc.publish_status != "draft":
        raise HTTPException(status_code=409, detail="Only draft documents can be submitted")

    title = (doc.doc_name or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    if not is_valid_tag(doc.doc_tag):
        raise HTTPException(status_code=400, detail="Tag is required")
    if not doc.file_storage_path or not (doc.file_name or "").strip():
        raise HTTPException(status_code=400, detail="At least one file is required")

    doc.publish_status = "review"
    db.commit()
    db.refresh(doc)
    return doc


def _apply_content_hash(
    doc: Document,
    storage: StorageService,
) -> None:
    """Set file_content_sha256 / file_type from the single attached file."""
    if not doc.file_storage_path:
        return
    try:
        data = storage.read_bytes(doc.file_storage_path)
    except FileNotFoundError:
        return
    doc.file_content_sha256 = content_sha256(data)
    if doc.file_name:
        doc.file_type = Path(doc.file_name).suffix.lower().lstrip(".") or doc.file_type


def _find_ready_duplicate(
    db: Session,
    *,
    tenant_id: UUID,
    content_hash: str | None,
    exclude_id: UUID,
    exclude_doc_group_id: UUID | None,
) -> Document | None:
    """Other logical doc (different doc_group) with same bytes already in KB."""
    if not content_hash:
        return None
    q = select(Document).where(
        Document.tenant_id == tenant_id,
        Document.file_content_sha256 == content_hash,
        Document.publish_status == "published",
        Document.ingest_status == "ready",
        Document.is_latest.is_(True),
        Document.deleted_at.is_(None),
        Document.doc_id != exclude_id,
    )
    if exclude_doc_group_id is not None:
        q = q.where(Document.doc_group_id != exclude_doc_group_id)
    return db.scalar(q.limit(1))


def publish_document(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
) -> PublishResult:
    """Publish a review document, enqueue ingest, and optionally run sync ingest."""
    doc = _get_document(db, document_id=document_id, tenant_id=tenant_id)
    if doc.publish_status != "review":
        raise HTTPException(status_code=409, detail="Only review documents can be published")

    storage = StorageService()
    _apply_content_hash(doc, storage)

    dup = _find_ready_duplicate(
        db,
        tenant_id=tenant_id,
        content_hash=doc.file_content_sha256,
        exclude_id=doc.doc_id,
        exclude_doc_group_id=doc.doc_group_id,
    )
    if dup is not None:
        # Revert to draft so Admin shows editable form; do not publish.
        doc.publish_status = "draft"
        db.commit()
        raise HTTPException(
            status_code=409,
            detail=duplicate_content_conflict_detail(
                existing_document_id=dup.doc_id,
                existing_title=dup.doc_name,
            ),
        )

    doc.publish_status = "published"
    doc.ingest_status = "pending"
    doc.error_message = None

    job = IngestJob(
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
    if settings.ingest_sync_on_publish:
        try:
            process_ingest_job(db, job.id)
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
        ingest_status="pending",
        version_number=new_ver,
        is_latest=True,
        file_type=old.file_type,
        file_storage_path=old.file_storage_path,
        file_name=old.file_name,
        file_content_type=old.file_content_type,
        file_size_bytes=int(old.file_size_bytes or 0),
        file_metadata=dict(old.file_metadata or {}),
    )
    db.add(draft)
    db.commit()
    return _get_document(db, document_id=draft.doc_id, tenant_id=tenant_id)


def latest_ingest_job(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
) -> IngestJob | None:
    """Return the most recent ingest job for the document in the tenant."""
    _get_document(db, document_id=document_id, tenant_id=tenant_id)
    return db.scalar(
        select(IngestJob)
        .where(
            IngestJob.doc_id == document_id,
            IngestJob.tenant_id == tenant_id,
        )
        .order_by(IngestJob.create_at.desc())
        .limit(1)
    )


def soft_delete_document(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
) -> Document:
    """Soft-delete all versions in the doc group and demote index rows."""
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
        mark_document_ingest_not_latest(
            db, tenant_id=tenant_id, document_id=row.doc_id
        )
    db.commit()
    db.refresh(doc)
    return doc
