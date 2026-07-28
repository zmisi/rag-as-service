"""Folder business logic with depth, cycle, uniqueness and emptiness checks (P2-F02)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rag_api.db.models.document import Document
from rag_api.db.models.folder import Folder
from rag_api.db.models.user import User
from rag_api.repositories.folder_repository import FolderRepository

MAX_DEPTH = 10

VISIBILITY_PUBLIC = "public"
VISIBILITY_PARTIAL = "partial"
VISIBILITY_PRIVATE = "private"
ALLOWED_VISIBILITY = frozenset(
    {VISIBILITY_PUBLIC, VISIBILITY_PARTIAL, VISIBILITY_PRIVATE}
)


def _doc_list_status(*, publish_status: str, ingest_status: str) -> str:
    """Map internal document states to admin list labels."""
    if publish_status == "draft":
        return "草稿"
    if publish_status == "review":
        return "待审核"
    if ingest_status in {"pending", "processing"}:
        return "待解析"
    if ingest_status == "ready":
        return "完成"
    return "待发布"


def _repo(db: Session) -> FolderRepository:
    return FolderRepository(db)


# ── helpers ──────────────────────────────────────────────────────────

def _depth_of(repo: FolderRepository, *, tenant_id: UUID, folder_id: UUID) -> int:
    """Return 1-based depth of *folder_id* (root children = 1)."""
    ancestors = repo.ancestor_ids(tenant_id=tenant_id, folder_id=folder_id)
    return len(ancestors)


def _would_cycle(
    repo: FolderRepository, *, tenant_id: UUID, folder_id: UUID, new_parent_id: UUID
) -> bool:
    """Return True if setting *folder_id*.parent = *new_parent_id* creates a cycle."""
    if new_parent_id == folder_id:
        return True
    current = new_parent_id
    seen: set[UUID] = set()
    while current is not None:
        if current == folder_id:
            return True
        if current in seen:
            break
        seen.add(current)
        parent = repo.get_by_id(tenant_id=tenant_id, folder_id=current)
        if parent is None:
            break
        current = parent.parent_id
    return False


def _subtree_max_depth(repo: FolderRepository, db: Session, *, tenant_id: UUID, folder_id: UUID) -> int:
    """Return the max depth of any descendant under *folder_id* (1 = leaf)."""
    children = repo.list_children(tenant_id=tenant_id, parent_id=folder_id)
    if not children:
        return 1
    return 1 + max(
        _subtree_max_depth(repo, db, tenant_id=tenant_id, folder_id=c.folder_id)
        for c in children
    )


def _has_documents(db: Session, *, tenant_id: UUID, folder_id: UUID) -> bool:
    """Return whether any document belongs to *folder_id*."""
    return db.execute(
        select(Document.doc_id).where(
            Document.tenant_id == tenant_id,
            Document.folder_id == folder_id,
            Document.deleted_at.is_(None),
        ).limit(1)
    ).first() is not None


# ── public API ───────────────────────────────────────────────────────

def create_folder(
    db: Session,
    *,
    tenant_id: UUID,
    name: str,
    parent_id: UUID | None = None,
    description: str = "",
    visibility: str = VISIBILITY_PRIVATE,
) -> Folder:
    """Create a folder under *parent_id* (``None`` = root).

    Raises 409 on duplicate name under the same parent (case-insensitive)
    and 422 if depth would exceed ``MAX_DEPTH``.
    ``visibility`` is stored metadata only (no ACL enforcement in P2-F02).
    """
    repo = _repo(db)
    if parent_id is not None:
        parent = repo.get_by_id(tenant_id=tenant_id, folder_id=parent_id)
        if parent is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "parent folder not found")
        parent_depth = _depth_of(repo, tenant_id=tenant_id, folder_id=parent_id)
        if parent_depth >= MAX_DEPTH:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"folder depth limit ({MAX_DEPTH}) exceeded",
            )

    vis = (visibility or VISIBILITY_PRIVATE).strip().lower()
    if vis not in ALLOWED_VISIBILITY:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "visibility must be public, partial, or private",
        )

    folder = Folder(
        tenant_id=tenant_id,
        parent_id=parent_id,
        name=name.strip(),
        description=(description or "").strip(),
        visibility=vis,
    )
    try:
        repo.create(folder)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "a folder with this name already exists under the same parent",
        )
    return folder


def update_folder(
    db: Session,
    *,
    tenant_id: UUID,
    folder_id: UUID,
    name: str | None = None,
    description: str | None = None,
    visibility: str | None = None,
) -> Folder:
    """Update folder name / description / visibility metadata."""
    repo = _repo(db)
    folder = repo.get_by_id(tenant_id=tenant_id, folder_id=folder_id)
    if folder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "folder not found")

    if name is not None:
        new_name = name.strip()
        if not new_name:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "name is required")
        folder.name = new_name
    if description is not None:
        folder.description = description.strip()
    if visibility is not None:
        vis = visibility.strip().lower()
        if vis not in ALLOWED_VISIBILITY:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "visibility must be public, partial, or private",
            )
        folder.visibility = vis

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "a folder with this name already exists under the same parent",
        )
    return folder


def rename_folder(
    db: Session,
    *,
    tenant_id: UUID,
    folder_id: UUID,
    new_name: str,
) -> Folder:
    """Rename a folder; raises 409 on duplicate name under the same parent."""
    repo = _repo(db)
    folder = repo.get_by_id(tenant_id=tenant_id, folder_id=folder_id)
    if folder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "folder not found")
    folder.name = new_name.strip()
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "a folder with this name already exists under the same parent",
        )
    return folder


def move_folder(
    db: Session,
    *,
    tenant_id: UUID,
    folder_id: UUID,
    new_parent_id: UUID | None,
) -> Folder:
    """Move a folder to a new parent (``None`` = root).

    Rejects cycles and moves that would exceed depth limit.
    """
    repo = _repo(db)
    folder = repo.get_by_id(tenant_id=tenant_id, folder_id=folder_id)
    if folder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "folder not found")

    if new_parent_id is not None:
        parent = repo.get_by_id(tenant_id=tenant_id, folder_id=new_parent_id)
        if parent is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "target parent folder not found")
        if _would_cycle(repo, tenant_id=tenant_id, folder_id=folder_id, new_parent_id=new_parent_id):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "move would create a cycle",
            )
        parent_depth = _depth_of(repo, tenant_id=tenant_id, folder_id=new_parent_id)
        subtree_depth = _subtree_max_depth(repo, db, tenant_id=tenant_id, folder_id=folder_id)
        if parent_depth + subtree_depth > MAX_DEPTH:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"folder depth limit ({MAX_DEPTH}) exceeded",
            )

    folder.parent_id = new_parent_id
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "a folder with this name already exists under the target parent",
        )
    return folder


def delete_folder(db: Session, *, tenant_id: UUID, folder_id: UUID) -> None:
    """Delete an empty folder; raises 409 if it still contains children or documents."""
    repo = _repo(db)
    folder = repo.get_by_id(tenant_id=tenant_id, folder_id=folder_id)
    if folder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "folder not found")

    if repo.has_children(tenant_id=tenant_id, folder_id=folder_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "folder is not empty (contains sub-folders)",
        )
    if _has_documents(db, tenant_id=tenant_id, folder_id=folder_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "folder is not empty (contains documents)",
        )
    repo.delete(folder)


def get_folder(db: Session, *, tenant_id: UUID, folder_id: UUID) -> Folder:
    """Get a single folder or raise 404."""
    repo = _repo(db)
    folder = repo.get_by_id(tenant_id=tenant_id, folder_id=folder_id)
    if folder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "folder not found")
    return folder


def list_tree(db: Session, *, tenant_id: UUID) -> list[dict]:
    """Return the full folder tree as a flat list of dicts with ``folder_id``, ``parent_id``, ``name``."""
    repo = _repo(db)
    folders = repo.list_all(tenant_id=tenant_id)
    return [
        {
            "folder_id": str(f.folder_id),
            "parent_id": str(f.parent_id) if f.parent_id else None,
            "name": f.name,
            "description": f.description or "",
            "visibility": f.visibility or VISIBILITY_PRIVATE,
        }
        for f in folders
    ]


def list_layer(
    db: Session,
    *,
    tenant_id: UUID,
    folder_id: UUID | None,
) -> dict:
    """Return sub-folders, documents, and breadcrumb for the given layer.

    ``folder_id=None`` means root.
    """
    repo = _repo(db)

    if folder_id is not None and repo.get_by_id(tenant_id=tenant_id, folder_id=folder_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "folder not found")

    sub_folders = repo.list_children(tenant_id=tenant_id, parent_id=folder_id)

    doc_stmt = (
        select(Document)
        .where(
            Document.tenant_id == tenant_id,
            Document.is_latest.is_(True),
            Document.deleted_at.is_(None),
        )
    )
    if folder_id is None:
        doc_stmt = doc_stmt.where(Document.folder_id.is_(None))
    else:
        doc_stmt = doc_stmt.where(Document.folder_id == folder_id)
    doc_stmt = doc_stmt.order_by(Document.doc_name)

    documents = list(db.execute(doc_stmt).scalars().all())
    user_ids = {
        d.created_by for d in documents
    } | {
        d.reviewed_by for d in documents if d.reviewed_by is not None
    }
    user_map: dict[UUID, User] = {}
    if user_ids:
        users = db.execute(select(User).where(User.user_id.in_(user_ids))).scalars().all()
        user_map = {u.user_id: u for u in users}

    breadcrumb: list[dict] = []
    if folder_id is not None:
        ancestor_ids = repo.ancestor_ids(tenant_id=tenant_id, folder_id=folder_id)
        for aid in reversed(ancestor_ids):
            f = repo.get_by_id(tenant_id=tenant_id, folder_id=aid)
            if f:
                breadcrumb.append({"folder_id": str(f.folder_id), "name": f.name})

    return {
        "folder_id": str(folder_id) if folder_id else None,
        "breadcrumb": breadcrumb,
        "folders": [
            {
                "folder_id": str(f.folder_id),
                "parent_id": str(f.parent_id) if f.parent_id else None,
                "name": f.name,
                "description": f.description or "",
                "visibility": f.visibility or VISIBILITY_PRIVATE,
            }
            for f in sub_folders
        ],
        "documents": [
            {
                "doc_id": str(d.doc_id),
                "doc_name": d.doc_name,
                "publish_status": d.publish_status,
                "ingest_status": d.ingest_status,
                "status_label": _doc_list_status(
                    publish_status=d.publish_status,
                    ingest_status=d.ingest_status,
                ),
                "folder_id": str(d.folder_id) if d.folder_id else None,
                "create_at": d.create_at.isoformat() if d.create_at else None,
                "uploader": user_map.get(d.created_by).user_name
                if user_map.get(d.created_by)
                else None,
                "reviewer": user_map.get(d.reviewed_by).user_name
                if d.reviewed_by and user_map.get(d.reviewed_by)
                else None,
                "reviewed_at": d.reviewed_at.isoformat() if d.reviewed_at else None,
                "review_comment": d.review_comment if d.reviewed_at else None,
            }
            for d in documents
        ],
    }


def list_review_tasks(
    db: Session,
    *,
    tenant_id: UUID,
    reviewer_user_id: UUID,
) -> list[dict]:
    """Return latest documents pending review for the current reviewer."""
    documents = list(
        db.execute(
            select(Document)
            .where(
                Document.tenant_id == tenant_id,
                Document.is_latest.is_(True),
                Document.deleted_at.is_(None),
                Document.publish_status == "review",
                Document.reviewed_by == reviewer_user_id,
            )
            .order_by(Document.create_at.desc(), Document.doc_name.asc())
        )
        .scalars()
        .all()
    )
    user_ids = {d.created_by for d in documents} | {
        d.reviewed_by for d in documents if d.reviewed_by is not None
    }
    user_map: dict[UUID, User] = {}
    if user_ids:
        users = db.execute(select(User).where(User.user_id.in_(user_ids))).scalars().all()
        user_map = {u.user_id: u for u in users}

    return [
        {
            "doc_id": str(d.doc_id),
            "doc_name": d.doc_name,
            "publish_status": d.publish_status,
            "ingest_status": d.ingest_status,
            "status_label": _doc_list_status(
                publish_status=d.publish_status,
                ingest_status=d.ingest_status,
            ),
            "folder_id": str(d.folder_id) if d.folder_id else None,
            "create_at": d.create_at.isoformat() if d.create_at else None,
            "uploader": user_map.get(d.created_by).user_name
            if user_map.get(d.created_by)
            else None,
            "reviewer": user_map.get(d.reviewed_by).user_name
            if d.reviewed_by and user_map.get(d.reviewed_by)
            else None,
            "reviewed_at": d.reviewed_at.isoformat() if d.reviewed_at else None,
            "review_comment": d.review_comment if d.reviewed_at else None,
        }
        for d in documents
    ]


def move_document_to_folder(
    db: Session,
    *,
    tenant_id: UUID,
    doc_id: UUID,
    folder_id: UUID | None,
) -> None:
    """Move a document to *folder_id* (``None`` = root).

    Only updates ``folder_id``; does not touch publish/ingest status.
    """
    if folder_id is not None:
        repo = _repo(db)
        target = repo.get_by_id(tenant_id=tenant_id, folder_id=folder_id)
        if target is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "target folder not found")

    doc = db.execute(
        select(Document).where(
            Document.tenant_id == tenant_id,
            Document.doc_id == doc_id,
            Document.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")

    doc.folder_id = folder_id
    db.flush()
