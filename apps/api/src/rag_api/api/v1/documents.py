"""F03 document routes."""

from __future__ import annotations

from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from rag_api.api.dependencies import AuthContext, require_tenant_member
from rag_api.api.schemas.documents import (
    DocumentDetailOut,
    DocumentSaveRequest,
    DocumentSummaryOut,
    IngestJobOut,
    document_to_detail,
    document_to_summary,
    ingest_job_to_out,
)
from rag_api.db.session import get_db
from rag_api.services import document_service as doc_svc
from rag_api.services.preview_service import build_preview
from rag_api.services.storage_service import StorageService

router = APIRouter(prefix="/documents", tags=["documents"])


def _storage() -> StorageService:
    return StorageService()


class SubmitReviewRequest(BaseModel):
    """Review submission metadata."""

    reviewer_user_id: UUID | None = None
    review_comment: str | None = None


class CompleteReviewRequest(BaseModel):
    """Reviewer decision for a document in review status."""

    decision: Literal["approve", "reject"]
    review_comment: str | None = None


class PublishReviewRequest(BaseModel):
    """Optional reviewer comment when publishing."""

    review_comment: str | None = None

@router.post("", response_model=DocumentSummaryOut, status_code=status.HTTP_201_CREATED)
def create_document(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> DocumentSummaryOut:
    doc = doc_svc.create_document(
        db, tenant_id=auth.tenant_id, user_id=auth.user_id
    )
    return document_to_summary(doc)


@router.get("", response_model=list[DocumentSummaryOut])
def list_documents(
    tag: str | None = Query(default=None),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> list[DocumentSummaryOut]:
    items = doc_svc.list_documents(db, tenant_id=auth.tenant_id, tag=tag)
    return [document_to_summary(d) for d in items]


@router.post("/ingest/run-pending", response_model=list[IngestJobOut])
def run_pending_ingest_jobs(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> list[IngestJobOut]:
    """Drain pending ingest_jobs for this tenant only (dev/ops helper)."""
    from rag_api.ingestion.worker import process_pending_ingest_jobs

    jobs = process_pending_ingest_jobs(db, limit=50, tenant_id=auth.tenant_id)
    return [ingest_job_to_out(j) for j in jobs]


@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> DocumentDetailOut:
    doc = doc_svc.get_document_detail(
        db, document_id=document_id, tenant_id=auth.tenant_id
    )
    return document_to_detail(doc)


@router.patch("/{document_id}", response_model=DocumentDetailOut)
def save_document(
    document_id: UUID,
    body: DocumentSaveRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> DocumentDetailOut:
    doc = doc_svc.save_draft(
        db,
        document_id=document_id,
        tenant_id=auth.tenant_id,
        title=body.title,
        tag=body.tag,
    )
    return document_to_detail(doc)


@router.post(
    "/{document_id}/files",
    response_model=DocumentDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    document_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
    storage: StorageService = Depends(_storage),
) -> DocumentDetailOut:
    data = await file.read()
    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="filename is required",
        )
    doc_svc.add_file(
        db,
        storage,
        document_id=document_id,
        tenant_id=auth.tenant_id,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    doc = doc_svc.get_document_detail(
        db, document_id=document_id, tenant_id=auth.tenant_id
    )
    return document_to_detail(doc)


@router.post("/{document_id}/submit-review", response_model=DocumentDetailOut)
def submit_for_review(
    document_id: UUID,
    body: SubmitReviewRequest | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> DocumentDetailOut:
    doc = doc_svc.submit_for_review(
        db,
        document_id=document_id,
        tenant_id=auth.tenant_id,
        reviewer_user_id=body.reviewer_user_id if body else None,
        review_comment=body.review_comment if body else None,
    )
    return document_to_detail(doc)


@router.post("/{document_id}/publish", response_model=DocumentDetailOut)
def publish_document(
    document_id: UUID,
    body: PublishReviewRequest | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> DocumentDetailOut:
    result = doc_svc.publish_document(
        db,
        document_id=document_id,
        tenant_id=auth.tenant_id,
        reviewer_user_id=auth.user_id,
        review_comment=body.review_comment if body else None,
    )
    return document_to_detail(
        result.document,
        warning_code=result.warning_code,
        warning=result.warning,
    )


@router.post("/{document_id}/complete-review", response_model=DocumentDetailOut)
def complete_review(
    document_id: UUID,
    body: CompleteReviewRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> DocumentDetailOut:
    """Approve (pending publish) or reject (back to draft) a document under review."""
    if body.decision == "approve":
        doc = doc_svc.approve_document(
            db,
            document_id=document_id,
            tenant_id=auth.tenant_id,
            reviewer_user_id=auth.user_id,
            review_comment=body.review_comment,
        )
        return document_to_detail(doc)
    doc = doc_svc.reject_document(
        db,
        document_id=document_id,
        tenant_id=auth.tenant_id,
        reviewer_user_id=auth.user_id,
        review_comment=body.review_comment,
    )
    return document_to_detail(doc)


@router.post("/{document_id}/new-version", response_model=DocumentDetailOut)
def new_version(
    document_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> DocumentDetailOut:
    doc = doc_svc.new_version(
        db, document_id=document_id, tenant_id=auth.tenant_id
    )
    return document_to_detail(doc)


@router.get("/{document_id}/ingest-status", response_model=IngestJobOut | None)
def ingest_status(
    document_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> IngestJobOut | None:
    job = doc_svc.latest_ingest_job(
        db, document_id=document_id, tenant_id=auth.tenant_id
    )
    if job is None:
        return None
    return ingest_job_to_out(job)


@router.get("/{document_id}/download")
def download_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
    storage: StorageService = Depends(_storage),
) -> Response:
    """Download the source file attached to a document version."""
    doc = doc_svc.get_document_detail(
        db, document_id=document_id, tenant_id=auth.tenant_id
    )
    if not doc.file_storage_path or not (doc.file_name or "").strip():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document has no uploaded file",
        )
    try:
        data = storage.read_bytes(doc.file_storage_path)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored file not found",
        ) from exc
    filename = doc.file_name or "download"
    ascii_name = filename.encode("ascii", "ignore").decode() or "download"
    disposition = (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        content=data,
        media_type=doc.file_content_type or "application/octet-stream",
        headers={"Content-Disposition": disposition},
    )


@router.get("/{document_id}/preview")
def preview_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
    storage: StorageService = Depends(_storage),
) -> Response:
    """Return a read-only preview (PDF stream, text, or Office HTML)."""
    payload = build_preview(
        db,
        document_id=document_id,
        tenant_id=auth.tenant_id,
        storage=storage,
    )
    return Response(
        content=payload.content,
        media_type=payload.media_type,
        headers={"Content-Disposition": payload.content_disposition},
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> None:
    doc_svc.soft_delete_document(
        db, document_id=document_id, tenant_id=auth.tenant_id
    )
