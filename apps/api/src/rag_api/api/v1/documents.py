"""F03 document routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from rag_api.api.dependencies import AuthContext, require_tenant_member
from rag_api.api.schemas.documents import (
    DocumentDetailOut,
    DocumentSaveRequest,
    DocumentSummaryOut,
    IndexJobOut,
)
from rag_api.db.session import get_db
from rag_api.services import document_service as doc_svc
from rag_api.services.storage_service import StorageService

router = APIRouter(prefix="/documents", tags=["documents"])


def _storage() -> StorageService:
    return StorageService()


@router.post("", response_model=DocumentSummaryOut, status_code=status.HTTP_201_CREATED)
def create_document(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> DocumentSummaryOut:
    doc = doc_svc.create_document(
        db, tenant_id=auth.tenant_id, user_id=auth.user_id
    )
    return DocumentSummaryOut.model_validate(doc)


@router.get("", response_model=list[DocumentSummaryOut])
def list_documents(
    tag: str | None = Query(default=None),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> list[DocumentSummaryOut]:
    items = doc_svc.list_documents(db, tenant_id=auth.tenant_id, tag=tag)
    return [DocumentSummaryOut.model_validate(d) for d in items]


@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> DocumentDetailOut:
    doc = doc_svc.get_document_detail(
        db, document_id=document_id, tenant_id=auth.tenant_id
    )
    return DocumentDetailOut.model_validate(doc)


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
    return DocumentDetailOut.model_validate(doc)


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
    filename = file.filename or "upload.bin"
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
    return DocumentDetailOut.model_validate(doc)


@router.post("/{document_id}/submit-review", response_model=DocumentDetailOut)
def submit_for_review(
    document_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> DocumentDetailOut:
    doc = doc_svc.submit_for_review(
        db, document_id=document_id, tenant_id=auth.tenant_id
    )
    return DocumentDetailOut.model_validate(doc)


@router.post("/{document_id}/publish", response_model=DocumentDetailOut)
def publish_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> DocumentDetailOut:
    doc = doc_svc.publish_document(
        db, document_id=document_id, tenant_id=auth.tenant_id
    )
    return DocumentDetailOut.model_validate(doc)


@router.post("/{document_id}/new-version", response_model=DocumentDetailOut)
def new_version(
    document_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> DocumentDetailOut:
    doc = doc_svc.new_version(
        db, document_id=document_id, tenant_id=auth.tenant_id
    )
    return DocumentDetailOut.model_validate(doc)


@router.get("/{document_id}/index-status", response_model=IndexJobOut | None)
def index_status(
    document_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> IndexJobOut | None:
    job = doc_svc.latest_index_job(
        db, document_id=document_id, tenant_id=auth.tenant_id
    )
    if job is None:
        return None
    return IndexJobOut.model_validate(job)
