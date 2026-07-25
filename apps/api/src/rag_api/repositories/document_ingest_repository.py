"""Persistence for document sections/chunks (ingest rewrite path)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from rag_api.db.models import Document


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


def _pg_text_array_literal(parts: list[str]) -> str:
    escaped: list[str] = []
    for p in parts:
        escaped.append('"' + p.replace("\\", "\\\\").replace('"', '\\"') + '"')
    return "{" + ",".join(escaped) + "}"


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PreparedLeaf:
    """One embedded leaf chunk ready for ``document_chunks`` insert."""

    content: str
    heading_path: list[str]
    embedding_text: str
    embedding: list[float]
    chunk_type: str


@dataclass(frozen=True)
class PreparedSection:
    """One section with optional leaf chunks ready for persist."""

    level: int
    title: str
    path: str
    parent_path: str | None
    content: str
    section_index: int
    leaves: tuple[PreparedLeaf, ...]


class DocumentIngestRepository:
    """Tenant-scoped writes for document ingest index rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_document(self, *, tenant_id: UUID, document_id: UUID) -> Document | None:
        """Load a document by id within the tenant, or None if missing."""
        return self._session.scalar(
            select(Document).where(
                Document.doc_id == document_id,
                Document.tenant_id == tenant_id,
            )
        )

    def mark_chunks_not_latest(
        self,
        *,
        tenant_id: UUID,
        document_id: UUID,
    ) -> int:
        """Set ``is_latest=false`` on this document's chunks; return rows updated."""
        result = self._session.execute(
            text(
                """
                UPDATE rag_service.document_chunks
                SET is_latest = false
                WHERE tenant_id = :tenant_id
                  AND doc_id = :document_id
                  AND is_latest = true
                """
            ),
            {"tenant_id": str(tenant_id), "document_id": str(document_id)},
        )
        return int(result.rowcount or 0)

    def mark_sections_not_latest(
        self,
        *,
        tenant_id: UUID,
        document_id: UUID,
    ) -> int:
        """Set ``is_latest=false`` on this document's sections; return rows updated."""
        result = self._session.execute(
            text(
                """
                UPDATE rag_service.document_sections
                SET is_latest = false
                WHERE tenant_id = :tenant_id
                  AND doc_id = :document_id
                  AND is_latest = true
                """
            ),
            {"tenant_id": str(tenant_id), "document_id": str(document_id)},
        )
        return int(result.rowcount or 0)

    def mark_document_ingest_not_latest(
        self,
        *,
        tenant_id: UUID,
        document_id: UUID,
    ) -> None:
        """Demote sections and chunks for one document version (not the document row)."""
        self.mark_chunks_not_latest(tenant_id=tenant_id, document_id=document_id)
        self.mark_sections_not_latest(tenant_id=tenant_id, document_id=document_id)

    def delete_chunks(self, *, tenant_id: UUID, document_id: UUID) -> None:
        """Delete all chunk rows for this document version (tenant-scoped)."""
        self._session.execute(
            text(
                """
                DELETE FROM rag_service.document_chunks
                WHERE tenant_id = CAST(:tenant_id AS uuid)
                  AND doc_id = CAST(:document_id AS uuid)
                """
            ),
            {"tenant_id": str(tenant_id), "document_id": str(document_id)},
        )

    def delete_sections(self, *, tenant_id: UUID, document_id: UUID) -> None:
        """Delete all section rows for this document version (tenant-scoped)."""
        self._session.execute(
            text(
                """
                DELETE FROM rag_service.document_sections
                WHERE tenant_id = CAST(:tenant_id AS uuid)
                  AND doc_id = CAST(:document_id AS uuid)
                """
            ),
            {"tenant_id": str(tenant_id), "document_id": str(document_id)},
        )

    def clear_for_rewrite(self, *, tenant_id: UUID, document_id: UUID) -> None:
        """Demote is_latest then remove all index rows for this document version."""
        self.mark_document_ingest_not_latest(
            tenant_id=tenant_id, document_id=document_id
        )
        self.delete_chunks(tenant_id=tenant_id, document_id=document_id)
        self.delete_sections(tenant_id=tenant_id, document_id=document_id)

    def mark_other_group_versions_not_latest(
        self,
        *,
        tenant_id: UUID,
        doc_group_id: UUID,
        keep_document_id: UUID,
    ) -> None:
        """Keep one document version as latest; demote siblings in the same doc_group.

        Sets other documents' ``is_latest=False`` and demotes their sections/chunks
        via ``mark_document_ingest_not_latest``. Does not modify ``keep_document_id``.
        """
        others = list(
            self._session.scalars(
                select(Document).where(
                    Document.tenant_id == tenant_id,
                    Document.doc_group_id == doc_group_id,
                    Document.doc_id != keep_document_id,
                )
            ).all()
        )
        for other in others:
            other.is_latest = False
            self.mark_document_ingest_not_latest(
                tenant_id=tenant_id, document_id=other.doc_id
            )

    def insert_prepared_index(
        self,
        *,
        tenant_id: UUID,
        document_id: UUID,
        sections: list[PreparedSection],
    ) -> int:
        """Insert sections + leaf chunks. Returns leaf count."""
        path_to_id: dict[str, str] = {}
        leaf_count = 0
        chunk_index = 0

        def _resolve_parent_id(parent_path: str | None) -> str | None:
            cur = parent_path
            while cur:
                found = path_to_id.get(cur)
                if found is not None:
                    return found
                if " > " not in cur:
                    return None
                cur = cur.rsplit(" > ", 1)[0]
            return None

        for section in sections:
            section_id = str(uuid4())
            parent_id = _resolve_parent_id(section.parent_path)
            self._session.execute(
                text(
                    """
                    INSERT INTO rag_service.document_sections
                      (id, tenant_id, doc_id, parent_id, level, title, path,
                       content, section_index, is_latest)
                    VALUES
                      (
                        CAST(:id AS uuid),
                        CAST(:tenant_id AS uuid),
                        CAST(:document_id AS uuid),
                        CAST(:parent_id AS uuid),
                        :level,
                        :title,
                        :path,
                        :content,
                        :section_index,
                        true
                      )
                    """
                ),
                {
                    "id": section_id,
                    "tenant_id": str(tenant_id),
                    "document_id": str(document_id),
                    "parent_id": parent_id,
                    "level": str(section.level),
                    "title": section.title,
                    "path": section.path,
                    "content": section.content,
                    "section_index": section.section_index,
                },
            )
            path_to_id[section.path] = section_id

            for leaf in section.leaves:
                self._session.execute(
                    text(
                        """
                        INSERT INTO rag_service.document_chunks
                          (chunk_id, tenant_id, doc_id, section_id, chunk_index,
                           heading_path, content, embedding_text, chunk_type,
                           content_hash, embedding, metadata_, is_latest)
                        VALUES
                          (
                            CAST(:id AS uuid),
                            CAST(:tenant_id AS uuid),
                            CAST(:document_id AS uuid),
                            CAST(:section_id AS uuid),
                            :chunk_index,
                            CAST(:heading_path AS text[]),
                            :content,
                            :embedding_text,
                            :chunk_type,
                            :content_hash,
                            CAST(:embedding AS vector),
                            '{}'::jsonb,
                            true
                          )
                        """
                    ),
                    {
                        "id": str(uuid4()),
                        "tenant_id": str(tenant_id),
                        "document_id": str(document_id),
                        "section_id": section_id,
                        "chunk_index": chunk_index,
                        "heading_path": _pg_text_array_literal(leaf.heading_path),
                        "content": leaf.content,
                        "embedding_text": leaf.embedding_text,
                        "chunk_type": leaf.chunk_type,
                        "content_hash": _sha256_text(leaf.content),
                        "embedding": _vector_literal(leaf.embedding),
                    },
                )
                chunk_index += 1
                leaf_count += 1

        return leaf_count
