"""P2-F02 folder admin routes."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_api.api.dependencies import (
    AuthContext,
    require_tenant_admin,
    require_tenant_member,
)
from rag_api.db.session import get_db
from rag_api.db.models import TenantMember, User
from rag_api.db.models.folder import Folder
from rag_api.services import folder_service as folder_svc

router = APIRouter(prefix="/folders", tags=["folders"])

Visibility = Literal["public", "partial", "private"]


class FolderCreate(BaseModel):
    """Body for creating a folder / knowledge base."""

    name: str = Field(..., min_length=1, max_length=255)
    parent_id: UUID | None = None
    description: str = Field(default="", max_length=2000)
    visibility: Visibility = "private"


class FolderUpdate(BaseModel):
    """Body for updating folder / knowledge-base metadata."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    visibility: Visibility | None = None


class FolderMove(BaseModel):
    """Body for moving a folder to a new parent."""

    parent_id: UUID | None = None


class FolderOut(BaseModel):
    """Folder in responses."""

    folder_id: UUID
    parent_id: UUID | None
    name: str
    description: str = ""
    visibility: Visibility = "private"


class DocMoveToFolder(BaseModel):
    """Body for moving a document into a folder (or root)."""

    folder_id: UUID | None = None


class ReviewerOut(BaseModel):
    """Tenant reviewer option for submit-review forms."""

    user_id: UUID
    name: str
    email: str


class ReviewTaskOut(BaseModel):
    """Document row for the current reviewer's pending task list."""

    doc_id: UUID
    doc_name: str
    publish_status: str
    ingest_status: str
    status_label: str
    folder_id: UUID | None = None
    create_at: str | None = None
    uploader: str | None = None
    reviewer: str | None = None
    reviewed_at: str | None = None
    review_comment: str | None = None


def _folder_out(folder: Folder) -> FolderOut:
    """Map ORM folder to API response."""
    return FolderOut(
        folder_id=folder.folder_id,
        parent_id=folder.parent_id,
        name=folder.name,
        description=folder.description or "",
        visibility=folder.visibility or "private",  # type: ignore[arg-type]
    )


@router.post("", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
def create_folder(
    body: FolderCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> FolderOut:
    """Create a new folder under *parent_id* (``null`` = root)."""
    f = folder_svc.create_folder(
        db,
        tenant_id=auth.tenant_id,
        name=body.name,
        parent_id=body.parent_id,
        description=body.description,
        visibility=body.visibility,
    )
    db.commit()
    return _folder_out(f)


@router.get("/tree")
def folder_tree(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> list[dict]:
    """Return the full folder tree as a flat list of nodes."""
    return folder_svc.list_tree(db, tenant_id=auth.tenant_id)


@router.get("/list")
def folder_list(
    folder_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> dict:
    """Return sub-folders, documents and breadcrumb for one layer."""
    return folder_svc.list_layer(db, tenant_id=auth.tenant_id, folder_id=folder_id)


@router.get("/reviewers", response_model=list[ReviewerOut])
def list_reviewers(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> list[ReviewerOut]:
    """Return tenant members as reviewer options."""
    rows = db.execute(
        select(TenantMember.user_id, TenantMember.member_name, User.email)
        .join(User, User.user_id == TenantMember.user_id)
        .where(
            TenantMember.tenant_id == auth.tenant_id,
            TenantMember.active == 1,
            User.active == 1,
        )
        .order_by(TenantMember.member_name.asc())
    ).all()
    return [
        ReviewerOut(user_id=row.user_id, name=row.member_name, email=row.email)
        for row in rows
    ]


@router.get("/review-tasks", response_model=list[ReviewTaskOut])
def list_review_tasks(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_admin),
) -> list[ReviewTaskOut]:
    """Return documents currently submitted to the current admin/owner for review."""
    return [
        ReviewTaskOut(**item)
        for item in folder_svc.list_review_tasks(
            db,
            tenant_id=auth.tenant_id,
            reviewer_user_id=auth.user_id,
        )
    ]


@router.patch("/documents/{doc_id}/move", status_code=status.HTTP_200_OK)
def move_document(
    doc_id: UUID,
    body: DocMoveToFolder,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> dict:
    """Move a document to a folder (or root when ``folder_id`` is ``null``)."""
    folder_svc.move_document_to_folder(
        db, tenant_id=auth.tenant_id, doc_id=doc_id, folder_id=body.folder_id
    )
    db.commit()
    return {"ok": True}


@router.patch("/{folder_id}", response_model=FolderOut)
def update_folder(
    folder_id: UUID,
    body: FolderUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> FolderOut:
    """Update folder name and optional description / visibility."""
    f = folder_svc.update_folder(
        db,
        tenant_id=auth.tenant_id,
        folder_id=folder_id,
        name=body.name,
        description=body.description,
        visibility=body.visibility,
    )
    db.commit()
    return _folder_out(f)


@router.patch("/{folder_id}/move", response_model=FolderOut)
def move_folder(
    folder_id: UUID,
    body: FolderMove,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> FolderOut:
    """Move a folder to a new parent (``null`` = root)."""
    f = folder_svc.move_folder(
        db, tenant_id=auth.tenant_id, folder_id=folder_id, new_parent_id=body.parent_id
    )
    db.commit()
    return _folder_out(f)


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> None:
    """Delete an empty folder."""
    folder_svc.delete_folder(db, tenant_id=auth.tenant_id, folder_id=folder_id)
    db.commit()
