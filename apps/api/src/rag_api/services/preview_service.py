"""Read-only document preview for Admin (PDF / text / Office HTML)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from rag_api.ingestion.office import OfficeParseError
from rag_api.services import document_service as doc_svc
from rag_api.services.office_html_preview import office_to_preview_html
from rag_api.services.storage_service import StorageService

_TEXT_SUFFIXES = frozenset({".txt", ".md"})
_OFFICE_SUFFIXES = frozenset({".docx", ".pptx", ".xlsx"})
_PDF_SUFFIX = ".pdf"


@dataclass(frozen=True, slots=True)
class PreviewPayload:
    """Bytes and headers for a document preview response."""

    content: bytes
    media_type: str
    content_disposition: str


def build_preview(
    db: Session,
    *,
    document_id: UUID,
    tenant_id: UUID,
    storage: StorageService,
) -> PreviewPayload:
    """Load the document file and return a read-only preview payload."""
    doc = doc_svc.get_document_detail(
        db, document_id=document_id, tenant_id=tenant_id
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

    filename = doc.file_name or "preview"
    suffix = Path(filename).suffix.lower()
    disposition = _inline_disposition(filename)

    if suffix == _PDF_SUFFIX:
        return PreviewPayload(
            content=data,
            media_type=doc.file_content_type or "application/pdf",
            content_disposition=disposition,
        )

    if suffix in _TEXT_SUFFIXES:
        return PreviewPayload(
            content=data,
            media_type="text/plain; charset=utf-8",
            content_disposition=disposition,
        )

    if suffix in _OFFICE_SUFFIXES:
        try:
            body = office_to_preview_html(filename, data)
        except OfficeParseError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to build Office preview: {exc}",
            ) from exc
        return PreviewPayload(
            content=body.encode("utf-8"),
            media_type="text/html; charset=utf-8",
            content_disposition=disposition,
        )

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail=f"Preview not supported for type: {suffix or 'unknown'}",
    )


def _inline_disposition(filename: str) -> str:
    """Build a Content-Disposition header that prefers inline display."""
    ascii_name = filename.encode("ascii", "ignore").decode() or "preview"
    return f'inline; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'
