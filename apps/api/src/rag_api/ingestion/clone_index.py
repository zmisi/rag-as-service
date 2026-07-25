"""Clone section/chunk index rows between documents (duplicate content_sha256)."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def clone_document_index(
    db: Session,
    *,
    tenant_id: UUID,
    source_document_id: UUID,
    target_document_id: UUID,
) -> tuple[int, int]:
    """Copy is_latest sections/chunks from source onto target (new ids).

    Skips re-embedding by copying vector values. Returns (section_count, chunk_count).
    """
    if source_document_id == target_document_id:
        raise ValueError("source and target document_id must differ")

    # Replace any prior rows on the target version.
    db.execute(
        text(
            """
            DELETE FROM rag_service.document_chunks
            WHERE tenant_id = CAST(:tenant_id AS uuid)
              AND doc_id = CAST(:document_id AS uuid)
            """
        ),
        {"tenant_id": str(tenant_id), "document_id": str(target_document_id)},
    )
    db.execute(
        text(
            """
            DELETE FROM rag_service.document_sections
            WHERE tenant_id = CAST(:tenant_id AS uuid)
              AND doc_id = CAST(:document_id AS uuid)
            """
        ),
        {"tenant_id": str(tenant_id), "document_id": str(target_document_id)},
    )

    sections = db.execute(
        text(
            """
            SELECT id, parent_id, level, title, path, content, section_index, is_latest
            FROM rag_service.document_sections
            WHERE tenant_id = CAST(:tenant_id AS uuid)
              AND doc_id = CAST(:source_id AS uuid)
              AND is_latest = true
            ORDER BY section_index ASC
            """
        ),
        {"tenant_id": str(tenant_id), "source_id": str(source_document_id)},
    ).mappings().all()

    id_map: dict[str, str] = {}
    for row in sections:
        id_map[str(row["id"])] = str(uuid4())

    for row in sections:
        old_id = str(row["id"])
        new_id = id_map[old_id]
        old_parent = row["parent_id"]
        new_parent = id_map.get(str(old_parent)) if old_parent is not None else None
        db.execute(
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
                "id": new_id,
                "tenant_id": str(tenant_id),
                "document_id": str(target_document_id),
                "parent_id": new_parent,
                "level": row["level"],
                "title": row["title"],
                "path": row["path"],
                "content": row["content"],
                "section_index": row["section_index"],
            },
        )

    chunks = db.execute(
        text(
            """
            SELECT chunk_id, section_id, chunk_index,
                   heading_path::text AS heading_path,
                   content, embedding_text, chunk_type, token_count, content_hash,
                   content_tsv, embedding::text AS embedding,
                   COALESCE(metadata_::text, '{}') AS metadata_
            FROM rag_service.document_chunks
            WHERE tenant_id = CAST(:tenant_id AS uuid)
              AND doc_id = CAST(:source_id AS uuid)
              AND is_latest = true
            ORDER BY chunk_index ASC
            """
        ),
        {"tenant_id": str(tenant_id), "source_id": str(source_document_id)},
    ).mappings().all()

    chunk_count = 0
    for row in chunks:
        old_section = str(row["section_id"]) if row["section_id"] is not None else None
        new_section = id_map.get(old_section) if old_section else None
        if old_section and new_section is None:
            logger.warning(
                "clone_index skip chunk %s: section %s not mapped",
                row["chunk_id"],
                old_section,
            )
            continue
        db.execute(
            text(
                """
                INSERT INTO rag_service.document_chunks
                  (chunk_id, tenant_id, doc_id, section_id, chunk_index, heading_path,
                   content, embedding_text, chunk_type, token_count, content_hash,
                   content_tsv, embedding, metadata_, is_latest)
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
                    :token_count,
                    :content_hash,
                    :content_tsv,
                    CAST(:embedding AS vector),
                    CAST(:metadata AS jsonb),
                    true
                  )
                """
            ),
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "document_id": str(target_document_id),
                "section_id": new_section,
                "chunk_index": row["chunk_index"],
                "heading_path": row["heading_path"],
                "content": row["content"],
                "embedding_text": row["embedding_text"],
                "chunk_type": row["chunk_type"],
                "token_count": row["token_count"],
                "content_hash": row["content_hash"],
                "content_tsv": row["content_tsv"],
                "embedding": row["embedding"],
                "metadata": row["metadata_"] or "{}",
            },
        )
        chunk_count += 1

    logger.info(
        "clone_index tenant=%s source=%s target=%s sections=%s chunks=%s",
        tenant_id,
        source_document_id,
        target_document_id,
        len(sections),
        chunk_count,
    )
    return len(sections), chunk_count
