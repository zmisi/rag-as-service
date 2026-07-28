"""Folder persistence operations scoped by tenant_id (P2-F02)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rag_api.db.models.folder import Folder


class FolderRepository:
    """CRUD helpers for the ``folders`` table, always filtered by tenant."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ── reads ────────────────────────────────────────────────────────

    def get_by_id(self, *, tenant_id: UUID, folder_id: UUID) -> Folder | None:
        """Return a single folder owned by *tenant_id*, or ``None``."""
        return self._db.execute(
            select(Folder).where(
                Folder.tenant_id == tenant_id,
                Folder.folder_id == folder_id,
            )
        ).scalar_one_or_none()

    def list_children(self, *, tenant_id: UUID, parent_id: UUID | None) -> list[Folder]:
        """Return direct child folders under *parent_id* (``None`` = root)."""
        stmt = select(Folder).where(
            Folder.tenant_id == tenant_id,
        )
        if parent_id is None:
            stmt = stmt.where(Folder.parent_id.is_(None))
        else:
            stmt = stmt.where(Folder.parent_id == parent_id)
        stmt = stmt.order_by(func.lower(Folder.name))
        return list(self._db.execute(stmt).scalars().all())

    def list_all(self, *, tenant_id: UUID) -> list[Folder]:
        """Return every folder for *tenant_id* (for building the full tree)."""
        return list(
            self._db.execute(
                select(Folder)
                .where(Folder.tenant_id == tenant_id)
                .order_by(func.lower(Folder.name))
            )
            .scalars()
            .all()
        )

    def has_children(self, *, tenant_id: UUID, folder_id: UUID) -> bool:
        """Return whether *folder_id* has any direct child folders."""
        return self._db.execute(
            select(Folder.folder_id).where(
                Folder.tenant_id == tenant_id,
                Folder.parent_id == folder_id,
            ).limit(1)
        ).first() is not None

    def ancestor_ids(self, *, tenant_id: UUID, folder_id: UUID) -> list[UUID]:
        """Walk parent pointers and return ancestor IDs from *folder_id* up to root.

        Used for breadcrumb generation and cycle / depth validation.
        """
        ids: list[UUID] = []
        current = folder_id
        seen: set[UUID] = set()
        while current is not None:
            if current in seen:
                break
            seen.add(current)
            row = self._db.execute(
                select(Folder.parent_id).where(
                    Folder.tenant_id == tenant_id,
                    Folder.folder_id == current,
                )
            ).first()
            if row is None:
                break
            ids.append(current)
            current = row[0]
        return ids

    # ── writes ───────────────────────────────────────────────────────

    def create(self, folder: Folder) -> Folder:
        """Persist a new folder and flush to obtain server defaults."""
        self._db.add(folder)
        self._db.flush()
        return folder

    def delete(self, folder: Folder) -> None:
        """Hard-delete a folder (caller must ensure it is empty)."""
        self._db.delete(folder)
        self._db.flush()
