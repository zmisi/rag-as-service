"""Ingest job orchestration: parse → sections → chunk → embed → repository persist."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from rag_api.config import get_settings
from rag_api.db.models import IngestJob
from rag_api.ingestion.chunker import chunk_text
from rag_api.ingestion.embedding import Embedder, get_embedder
from rag_api.ingestion.file_metadata import (
    apply_modified_at_from_metadata,
    extract_document_properties,
    merge_file_metadata,
)
from rag_api.ingestion.parse import DocumentParser, ParseError, parse_files_to_markdown
from rag_api.ingestion.sections import (
    SectionDraft,
    build_section_tree,
    infer_chunk_type,
)
from rag_api.repositories.document_ingest_repository import (
    DocumentIngestRepository,
    PreparedLeaf,
    PreparedSection,
)
from rag_api.repositories.ingest_job_repository import IngestJobRepository
from rag_api.services.storage_service import StorageService

logger = logging.getLogger(__name__)


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


def mark_chunks_not_latest(
    db: Session,
    *,
    tenant_id: UUID,
    document_id: UUID,
) -> int:
    """Set ``is_latest=False`` on all chunks for the document within tenant."""
    return DocumentIngestRepository(db).mark_chunks_not_latest(
        tenant_id=tenant_id, document_id=document_id
    )


def mark_sections_not_latest(
    db: Session,
    *,
    tenant_id: UUID,
    document_id: UUID,
) -> int:
    """Set ``is_latest=False`` on all sections for the document within tenant."""
    return DocumentIngestRepository(db).mark_sections_not_latest(
        tenant_id=tenant_id, document_id=document_id
    )


def mark_document_ingest_not_latest(
    db: Session,
    *,
    tenant_id: UUID,
    document_id: UUID,
) -> None:
    """Demote document ingest rows and nested sections/chunks for the tenant."""
    DocumentIngestRepository(db).mark_document_ingest_not_latest(
        tenant_id=tenant_id, document_id=document_id
    )


# Back-compat aliases for callers still using deactivate_* names.
deactivate_document_chunks = mark_chunks_not_latest
deactivate_document_sections = mark_sections_not_latest
deactivate_document_ingest = mark_document_ingest_not_latest


def prepare_sections_for_persist(
    drafts: list[SectionDraft],
    *,
    embedder: Embedder,
    target_tokens: int,
    overlap_tokens: int,
) -> list[PreparedSection]:
    """Chunk + embed in memory; returns rows ready for DocumentIngestRepository."""
    embed_inputs: list[str] = []
    leaf_refs: list[tuple[int, str, list[str]]] = []  # section_idx, content, heading

    for section_index, draft in enumerate(drafts):
        pieces = chunk_text(
            draft.content,
            target_tokens=target_tokens,
            overlap_tokens=overlap_tokens,
        )
        heading = _heading_path(draft.path)
        for piece in pieces:
            leaf_refs.append((section_index, piece, heading))
            embed_inputs.append(build_embedding_text(heading, piece))

    vectors = embedder.embed(embed_inputs) if embed_inputs else []
    leaves_by_section: list[list[PreparedLeaf]] = [[] for _ in drafts]
    for (section_index, content, heading), emb_text, vec in zip(
        leaf_refs, embed_inputs, vectors, strict=True
    ):
        leaves_by_section[section_index].append(
            PreparedLeaf(
                content=content,
                heading_path=heading,
                embedding_text=emb_text,
                embedding=vec,
                chunk_type=infer_chunk_type(content),
            )
        )

    return [
        PreparedSection(
            level=draft.level,
            title=draft.title,
            path=draft.path,
            parent_path=draft.parent_path,
            content=draft.content,
            section_index=section_index,
            leaves=tuple(leaves_by_section[section_index]),
        )
        for section_index, draft in enumerate(drafts)
    ]


def reclaim_stuck_ingest_jobs(
    db: Session,
    *,
    older_than_seconds: int | None = None,
    tenant_id: UUID | None = None,
) -> int:
    """Reset running jobs stuck past the threshold back to pending."""
    return IngestJobRepository(db).reclaim_stuck(
        older_than_seconds=older_than_seconds,
        tenant_id=tenant_id,
    )


def claim_pending_ingest_jobs(
    db: Session,
    *,
    limit: int = 20,
    tenant_id: UUID | None = None,
) -> list[UUID]:
    """Claim pending jobs with ``FOR UPDATE SKIP LOCKED``; returns claimed job IDs."""
    return IngestJobRepository(db).claim_pending(limit=limit, tenant_id=tenant_id)


def process_ingest_job(
    db: Session,
    job_id: UUID,
    *,
    embedder: Embedder | None = None,
    storage: StorageService | None = None,
    parser: DocumentParser | None = None,
    already_claimed: bool = False,
) -> IngestJob:
    """Run full ingest pipeline for one job; marks succeeded or failed on the document."""
    jobs = IngestJobRepository(db)
    docs = DocumentIngestRepository(db)

    job = jobs.get(job_id)
    if job is None:
        raise ValueError(f"ingest_job not found: {job_id}")

    if not already_claimed:
        jobs.mark_running(job, increment_attempt=True)
        db.commit()

    settings = get_settings()
    embedder = embedder or get_embedder()
    storage = storage or StorageService()

    try:
        doc = docs.get_document(tenant_id=job.tenant_id, document_id=job.doc_id)
        if doc is None:
            raise ParseError("document missing")

        if doc.publish_status != "published" or doc.deleted_at is not None:
            docs.mark_document_ingest_not_latest(
                tenant_id=job.tenant_id, document_id=job.doc_id
            )
            jobs.mark_succeeded(job, error="skipped: document not published")
            db.commit()
            db.refresh(job)
            return job

        doc.ingest_status = "processing"
        doc.error_message = None
        db.commit()

        if not doc.file_storage_path:
            raise ParseError("no files attached")

        raw = storage.read_bytes(doc.file_storage_path)
        fname = (doc.file_name or "").strip()
        if not fname:
            raise ParseError("document file_name is required")
        doc_props = extract_document_properties(fname, raw)
        if doc_props:
            doc.file_metadata = merge_file_metadata(
                dict(doc.file_metadata or {}),
                document=doc_props,
            )
            mod = apply_modified_at_from_metadata(doc.file_metadata)
            if mod is not None:
                doc.file_modified_at = mod
        payloads: list[tuple[str, bytes]] = [(fname, raw)]

        markdown = parse_files_to_markdown(payloads, parser=parser)
        title_fallback = (doc.doc_name or "").strip() or fname
        drafts = build_section_tree(markdown, title_fallback=title_fallback)

        docs.clear_for_rewrite(tenant_id=job.tenant_id, document_id=job.doc_id)

        leaf_count = 0
        if drafts:
            prepared = prepare_sections_for_persist(
                drafts,
                embedder=embedder,
                target_tokens=settings.chunk_target_tokens,
                overlap_tokens=settings.chunk_overlap_tokens,
            )
            leaf_count = docs.insert_prepared_index(
                tenant_id=job.tenant_id,
                document_id=job.doc_id,
                sections=prepared,
            )

        provider = "qwen" if settings.qwen_embedding_enabled else "hashing"
        doc.embedding_provider = provider
        doc.embedding_model = settings.qwen_embedding_model
        doc.embedding_dimension = settings.embedding_dim
        doc.ingest_status = "ready"
        doc.error_message = None
        doc.is_latest = True
        docs.mark_other_group_versions_not_latest(
            tenant_id=job.tenant_id,
            doc_group_id=doc.doc_group_id,
            keep_document_id=doc.doc_id,
        )

        jobs.mark_succeeded(job)
        db.commit()
        logger.info(
            "ingest_job succeeded id=%s document_id=%s version=%s sections=%s leaves=%s",
            job.id,
            job.doc_id,
            job.version,
            len(drafts),
            leaf_count,
        )
    except Exception as exc:  # noqa: BLE001 — persist failure on job
        logger.exception("ingest_job failed id=%s", job_id)
        db.rollback()
        job = jobs.get(job_id)
        if job is not None:
            jobs.mark_failed(job, error=str(exc))
            failed_doc = docs.get_document(
                tenant_id=job.tenant_id, document_id=job.doc_id
            )
            if failed_doc is not None:
                failed_doc.ingest_status = "failed"
                failed_doc.error_message = str(exc)[:2000]
            db.commit()
        raise

    db.refresh(job)
    return job


def process_pending_ingest_jobs(
    db: Session,
    *,
    limit: int = 20,
    tenant_id: UUID | None = None,
    embedder: Embedder | None = None,
    storage: StorageService | None = None,
    parser: DocumentParser | None = None,
) -> list[IngestJob]:
    """Claim up to ``limit`` pending jobs and process each; returns finished job rows."""
    claimed = claim_pending_ingest_jobs(db, limit=limit, tenant_id=tenant_id)
    jobs = IngestJobRepository(db)
    done: list[IngestJob] = []
    for job_id in claimed:
        try:
            done.append(
                process_ingest_job(
                    db,
                    job_id,
                    embedder=embedder,
                    storage=storage,
                    parser=parser,
                    already_claimed=True,
                )
            )
        except Exception:  # noqa: BLE001 — continue queue
            refreshed = jobs.get(job_id)
            if refreshed is not None:
                done.append(refreshed)
    return done
