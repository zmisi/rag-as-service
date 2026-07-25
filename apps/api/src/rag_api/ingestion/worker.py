"""Index job worker: parse → H1–H6 sections → leaf chunk → embed → pgvector."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from rag_api.config import get_settings
from rag_api.db.models import Document, IndexJob
from rag_api.domain.documents.constants import INDEX_JOB_ERROR_DUPLICATE_CONTENT_SHA256
from rag_api.indexing.chunker import chunk_text
from rag_api.indexing.clone_index import clone_document_index
from rag_api.indexing.embedding import Embedder, get_embedder
from rag_api.indexing.parse import DocumentParser, ParseError, parse_files_to_markdown
from rag_api.indexing.sections import (
    SectionDraft,
    build_section_tree,
    infer_chunk_type,
)
from rag_api.services.storage_service import StorageService

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


def _heading_path(path: str) -> list[str]:
    parts = [p.strip() for p in (path or "").split(" > ") if p.strip()]
    return parts


def build_embedding_text(heading_path: list[str], content: str) -> str:
    """Text sent to the embedder: path context + leaf body (industry practice)."""
    body = (content or "").strip()
    parts = [p.strip() for p in heading_path if p and str(p).strip()]
    if not parts:
        return body
    prefix = " > ".join(parts)
    if not body:
        return prefix
    return f"{prefix}\n\n{body}"


def _pg_text_array_literal(parts: list[str]) -> str:
    """Format a Python list as a PostgreSQL text[] literal."""
    escaped: list[str] = []
    for p in parts:
        escaped.append('"' + p.replace("\\", "\\\\").replace('"', '\\"') + '"')
    return "{" + ",".join(escaped) + "}"


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def mark_chunks_not_latest(
    db: Session,
    *,
    tenant_id: UUID,
    document_id: UUID,
) -> int:
    result = db.execute(
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
    db: Session,
    *,
    tenant_id: UUID,
    document_id: UUID,
) -> int:
    result = db.execute(
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


def mark_document_index_not_latest(
    db: Session,
    *,
    tenant_id: UUID,
    document_id: UUID,
) -> None:
    mark_chunks_not_latest(db, tenant_id=tenant_id, document_id=document_id)
    mark_sections_not_latest(db, tenant_id=tenant_id, document_id=document_id)


# Back-compat aliases for callers still using deactivate_* names.
deactivate_document_chunks = mark_chunks_not_latest
deactivate_document_sections = mark_sections_not_latest
deactivate_document_index = mark_document_index_not_latest


def _mark_other_group_versions_not_latest(
    db: Session,
    *,
    tenant_id: UUID,
    doc_group_id: UUID,
    keep_document_id: UUID,
) -> None:
    others = list(
        db.scalars(
            select(Document).where(
                Document.tenant_id == tenant_id,
                Document.doc_group_id == doc_group_id,
                Document.doc_id != keep_document_id,
            )
        ).all()
    )
    for other in others:
        other.is_latest = False
        mark_document_index_not_latest(
            db, tenant_id=tenant_id, document_id=other.doc_id
        )


def _persist_sections_and_leaves(
    db: Session,
    *,
    tenant_id: UUID,
    document_id: UUID,
    drafts: list[SectionDraft],
    embedder: Embedder,
    target_tokens: int,
    overlap_tokens: int,
) -> int:
    """Insert sections + leaf chunks. Returns leaf count."""
    path_to_id: dict[str, str] = {}
    leaf_count = 0
    all_leaf_texts: list[tuple[str, str, list[str]]] = []  # section_id, content, heading_path
    chunk_index = 0

    def _resolve_parent_id(parent_path: str | None) -> str | None:
        """Walk up path ancestors until a persisted section is found."""
        cur = parent_path
        while cur:
            found = path_to_id.get(cur)
            if found is not None:
                return found
            if " > " not in cur:
                return None
            cur = cur.rsplit(" > ", 1)[0]
        return None

    for section_index, draft in enumerate(drafts):
        section_id = str(uuid4())
        parent_id = _resolve_parent_id(draft.parent_path)
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
                "id": section_id,
                "tenant_id": str(tenant_id),
                "document_id": str(document_id),
                "parent_id": parent_id,
                "level": str(draft.level),
                "title": draft.title,
                "path": draft.path,
                "content": draft.content,
                "section_index": section_index,
            },
        )
        path_to_id[draft.path] = section_id

        pieces = chunk_text(
            draft.content,
            target_tokens=target_tokens,
            overlap_tokens=overlap_tokens,
        )
        heading = _heading_path(draft.path)
        for piece in pieces:
            all_leaf_texts.append((section_id, piece, heading))

    if not all_leaf_texts:
        return 0

    embed_inputs = [
        build_embedding_text(heading, content)
        for _section_id, content, heading in all_leaf_texts
    ]
    vectors = embedder.embed(embed_inputs)
    for (section_id, content, heading), emb_text, vec in zip(
        all_leaf_texts, embed_inputs, vectors, strict=True
    ):
        db.execute(
            text(
                """
                INSERT INTO rag_service.document_chunks
                  (chunk_id, tenant_id, doc_id, section_id, chunk_index, heading_path,
                   content, embedding_text, chunk_type, content_hash, embedding,
                   metadata_, is_latest)
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
                "heading_path": _pg_text_array_literal(heading),
                "content": content,
                "embedding_text": emb_text,
                "chunk_type": infer_chunk_type(content),
                "content_hash": _sha256_text(content),
                "embedding": _vector_literal(vec),
            },
        )
        chunk_index += 1
        leaf_count += 1
    return leaf_count


def reclaim_stuck_index_jobs(
    db: Session,
    *,
    older_than_seconds: int | None = None,
    tenant_id: UUID | None = None,
) -> int:
    """Reset long-running jobs back to pending so workers can retry."""
    settings = get_settings()
    seconds = (
        older_than_seconds
        if older_than_seconds is not None
        else settings.index_job_stuck_after_seconds
    )
    params: dict[str, object] = {"seconds": int(seconds)}
    tenant_clause = ""
    if tenant_id is not None:
        tenant_clause = "AND tenant_id = CAST(:tenant_id AS uuid)"
        params["tenant_id"] = str(tenant_id)
    result = db.execute(
        text(
            f"""
            UPDATE rag_service.index_jobs
            SET status = 'pending',
                error = 'reclaimed: stuck running',
                finished_at = NULL
            WHERE status = 'running'
              AND started_at IS NOT NULL
              AND started_at < (now() AT TIME ZONE 'utc')
                    - make_interval(secs => :seconds)
              {tenant_clause}
            """
        ),
        params,
    )
    db.commit()
    return int(result.rowcount or 0)


def claim_pending_index_jobs(
    db: Session,
    *,
    limit: int = 20,
    tenant_id: UUID | None = None,
) -> list[UUID]:
    """Claim pending jobs with ``FOR UPDATE SKIP LOCKED`` (multi-worker safe)."""
    reclaim_stuck_index_jobs(db, tenant_id=tenant_id)

    params: dict[str, object] = {"limit": int(limit)}
    tenant_clause = ""
    if tenant_id is not None:
        tenant_clause = "AND tenant_id = CAST(:tenant_id AS uuid)"
        params["tenant_id"] = str(tenant_id)

    rows = db.execute(
        text(
            f"""
            SELECT id
            FROM rag_service.index_jobs
            WHERE status = 'pending'
              {tenant_clause}
            ORDER BY create_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT :limit
            """
        ),
        params,
    ).fetchall()
    ids = [UUID(str(r[0])) for r in rows]
    if not ids:
        db.commit()
        return []

    now = _now()
    for job_id in ids:
        job = db.get(IndexJob, job_id)
        if job is None or job.status != "pending":
            continue
        job.status = "running"
        job.started_at = now
        job.attempt_count = int(job.attempt_count or 0) + 1
        job.error = None
        job.finished_at = None
    db.commit()
    return ids


def process_index_job(
    db: Session,
    job_id: UUID,
    *,
    embedder: Embedder | None = None,
    storage: StorageService | None = None,
    parser: DocumentParser | None = None,
    already_claimed: bool = False,
) -> IndexJob:
    job = db.get(IndexJob, job_id)
    if job is None:
        raise ValueError(f"index_job not found: {job_id}")

    if not already_claimed:
        job.status = "running"
        job.started_at = _now()
        job.attempt_count = int(job.attempt_count or 0) + 1
        job.error = None
        db.commit()

    settings = get_settings()
    embedder = embedder or get_embedder()
    storage = storage or StorageService()

    try:
        doc = db.scalar(
            select(Document)
            .where(Document.doc_id == job.doc_id, Document.tenant_id == job.tenant_id)
            .options(selectinload(Document.files))
        )
        if doc is None:
            raise ParseError("document missing")

        if doc.publish_status != "published" or doc.deleted_at is not None:
            mark_document_index_not_latest(
                db, tenant_id=job.tenant_id, document_id=job.doc_id
            )
            job.status = "succeeded"
            job.finished_at = _now()
            job.error = "skipped: document not published"
            db.commit()
            db.refresh(job)
            return job

        doc.index_status = "processing"
        doc.error_message = None
        db.commit()

        # Same-tenant content hash: clone index, skip re-embed.
        if doc.content_sha256:
            dup = db.scalar(
                select(Document)
                .where(
                    Document.tenant_id == job.tenant_id,
                    Document.content_sha256 == doc.content_sha256,
                    Document.index_status == "ready",
                    Document.is_latest.is_(True),
                    Document.deleted_at.is_(None),
                    Document.doc_id != doc.doc_id,
                )
                .limit(1)
            )
            if dup is not None:
                clone_document_index(
                    db,
                    tenant_id=job.tenant_id,
                    source_document_id=dup.doc_id,
                    target_document_id=doc.doc_id,
                )
                doc.index_status = "ready"
                doc.error_message = None
                doc.embedding_provider = dup.embedding_provider
                doc.embedding_model = dup.embedding_model
                doc.embedding_dimension = dup.embedding_dimension
                doc.is_latest = True
                _mark_other_group_versions_not_latest(
                    db,
                    tenant_id=job.tenant_id,
                    doc_group_id=doc.doc_group_id,
                    keep_document_id=doc.doc_id,
                )
                job.status = "succeeded"
                job.finished_at = _now()
                job.error = INDEX_JOB_ERROR_DUPLICATE_CONTENT_SHA256
                db.commit()
                db.refresh(job)
                return job

        files = [f for f in doc.files if f.version == job.version]
        if not files:
            files = list(doc.files)
        if not files:
            raise ParseError("no files attached")

        payloads: list[tuple[str, bytes]] = []
        for f in files:
            raw = storage.read_bytes(f.storage_key)
            payloads.append((f.filename, raw))

        markdown = parse_files_to_markdown(payloads, parser=parser)
        title_fallback = (doc.doc_name or "").strip() or (
            files[0].filename if files else "文档"
        )
        drafts = build_section_tree(markdown, title_fallback=title_fallback)

        # Clear any prior index rows for this version document_id before rewrite.
        mark_document_index_not_latest(
            db, tenant_id=job.tenant_id, document_id=job.doc_id
        )
        db.execute(
            text(
                """
                DELETE FROM rag_service.document_chunks
                WHERE tenant_id = CAST(:tenant_id AS uuid)
                  AND doc_id = CAST(:document_id AS uuid)
                """
            ),
            {"tenant_id": str(job.tenant_id), "document_id": str(job.doc_id)},
        )
        db.execute(
            text(
                """
                DELETE FROM rag_service.document_sections
                WHERE tenant_id = CAST(:tenant_id AS uuid)
                  AND doc_id = CAST(:document_id AS uuid)
                """
            ),
            {"tenant_id": str(job.tenant_id), "document_id": str(job.doc_id)},
        )

        leaf_count = 0
        if drafts:
            leaf_count = _persist_sections_and_leaves(
                db,
                tenant_id=job.tenant_id,
                document_id=job.doc_id,
                drafts=drafts,
                embedder=embedder,
                target_tokens=settings.chunk_target_tokens,
                overlap_tokens=settings.chunk_overlap_tokens,
            )

        # Embedding audit on document only.
        provider = "qwen" if settings.qwen_embedding_enabled else "hashing"
        doc.embedding_provider = provider
        doc.embedding_model = settings.qwen_embedding_model
        doc.embedding_dimension = settings.embedding_dim
        doc.index_status = "ready"
        doc.error_message = None
        doc.is_latest = True
        _mark_other_group_versions_not_latest(
            db,
            tenant_id=job.tenant_id,
            doc_group_id=doc.doc_group_id,
            keep_document_id=doc.doc_id,
        )

        job.status = "succeeded"
        job.finished_at = _now()
        job.error = None
        db.commit()
        logger.info(
            "index_job succeeded id=%s document_id=%s version=%s sections=%s leaves=%s",
            job.id,
            job.doc_id,
            job.version,
            len(drafts),
            leaf_count,
        )
    except Exception as exc:  # noqa: BLE001 — persist failure on job
        logger.exception("index_job failed id=%s", job_id)
        db.rollback()
        job = db.get(IndexJob, job_id)
        if job is not None:
            job.status = "failed"
            job.finished_at = _now()
            job.error = str(exc)[:2000]
            doc = db.get(Document, job.doc_id)
            if doc is not None and doc.tenant_id == job.tenant_id:
                doc.index_status = "failed"
                doc.error_message = str(exc)[:2000]
            db.commit()
        raise

    db.refresh(job)
    return job


def process_pending_jobs(
    db: Session,
    *,
    limit: int = 20,
    tenant_id: UUID | None = None,
    embedder: Embedder | None = None,
    storage: StorageService | None = None,
    parser: DocumentParser | None = None,
) -> list[IndexJob]:
    claimed = claim_pending_index_jobs(db, limit=limit, tenant_id=tenant_id)
    done: list[IndexJob] = []
    for job_id in claimed:
        try:
            done.append(
                process_index_job(
                    db,
                    job_id,
                    embedder=embedder,
                    storage=storage,
                    parser=parser,
                    already_claimed=True,
                )
            )
        except Exception:  # noqa: BLE001 — continue queue
            refreshed = db.get(IndexJob, job_id)
            if refreshed is not None:
                done.append(refreshed)
    return done
