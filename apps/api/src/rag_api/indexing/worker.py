"""Index job worker: parse → chunk → embed → write pgvector chunks."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from rag_api.db.models import Document, IndexJob
from rag_api.indexing.chunker import chunk_text
from rag_api.indexing.embedding import Embedder, get_embedder
from rag_api.indexing.parse import ParseError, extract_text
from rag_api.services.storage_service import StorageService

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


def deactivate_document_chunks(
    db: Session,
    *,
    tenant_id: UUID,
    document_id: UUID,
) -> int:
    result = db.execute(
        text(
            """
            UPDATE rag_service.document_chunks
            SET is_active = false
            WHERE tenant_id = :tenant_id
              AND document_id = :document_id
              AND is_active = true
            """
        ),
        {"tenant_id": str(tenant_id), "document_id": str(document_id)},
    )
    return int(result.rowcount or 0)


def process_index_job(
    db: Session,
    job_id: UUID,
    *,
    embedder: Embedder | None = None,
    storage: StorageService | None = None,
) -> IndexJob:
    job = db.get(IndexJob, job_id)
    if job is None:
        raise ValueError(f"index_job not found: {job_id}")

    job.status = "running"
    job.started_at = _now()
    job.attempt_count = int(job.attempt_count or 0) + 1
    job.error = None
    db.commit()

    embedder = embedder or get_embedder()
    storage = storage or StorageService()

    try:
        doc = db.scalar(
            select(Document)
            .where(Document.id == job.document_id, Document.tenant_id == job.tenant_id)
            .options(selectinload(Document.files))
        )
        if doc is None:
            raise ParseError("document missing")
        if doc.status != "published" or doc.deleted_at is not None:
            # Spec F04-T02: no active chunks for non-published
            deactivate_document_chunks(
                db, tenant_id=job.tenant_id, document_id=job.document_id
            )
            job.status = "succeeded"
            job.finished_at = _now()
            job.error = "skipped: document not published"
            db.commit()
            db.refresh(job)
            return job

        files = [f for f in doc.files if f.version == job.version]
        if not files:
            files = list(doc.files)
        if not files:
            raise ParseError("no files attached")

        texts: list[str] = []
        for f in files:
            raw = storage.read_bytes(f.storage_key)
            texts.append(extract_text(f.filename, raw))
        combined = "\n\n".join(t for t in texts if t.strip()).strip()
        pieces = chunk_text(combined)

        # Replace prior versions for this document
        deactivate_document_chunks(
            db, tenant_id=job.tenant_id, document_id=job.document_id
        )

        if pieces:
            vectors = embedder.embed(pieces)
            for ordinal, (content, vec) in enumerate(zip(pieces, vectors, strict=True)):
                chunk_id = str(uuid4())
                db.execute(
                    text(
                        """
                        INSERT INTO rag_service.document_chunks
                          (id, tenant_id, document_id, version, ordinal, content, embedding, is_active)
                        VALUES
                          (
                            CAST(:id AS uuid),
                            CAST(:tenant_id AS uuid),
                            CAST(:document_id AS uuid),
                            :version,
                            :ordinal,
                            :content,
                            CAST(:embedding AS vector),
                            true
                          )
                        """
                    ),
                    {
                        "id": chunk_id,
                        "tenant_id": str(job.tenant_id),
                        "document_id": str(job.document_id),
                        "version": job.version,
                        "ordinal": ordinal,
                        "content": content,
                        "embedding": _vector_literal(vec),
                    },
                )

        job.status = "succeeded"
        job.finished_at = _now()
        job.error = None
        db.commit()
        logger.info(
            "index_job succeeded id=%s document_id=%s version=%s chunks=%s",
            job.id,
            job.document_id,
            job.version,
            len(pieces),
        )
    except Exception as exc:  # noqa: BLE001 — persist failure on job
        logger.exception("index_job failed id=%s", job_id)
        db.rollback()
        job = db.get(IndexJob, job_id)
        if job is not None:
            job.status = "failed"
            job.finished_at = _now()
            job.error = str(exc)[:2000]
            db.commit()
        raise

    db.refresh(job)
    return job


def process_pending_jobs(
    db: Session,
    *,
    limit: int = 20,
    embedder: Embedder | None = None,
    storage: StorageService | None = None,
) -> list[IndexJob]:
    jobs = list(
        db.scalars(
            select(IndexJob)
            .where(IndexJob.status == "pending")
            .order_by(IndexJob.create_at.asc())
            .limit(limit)
        ).all()
    )
    done: list[IndexJob] = []
    for job in jobs:
        try:
            done.append(
                process_index_job(db, job.id, embedder=embedder, storage=storage)
            )
        except Exception:  # noqa: BLE001 — continue queue
            refreshed = db.get(IndexJob, job.id)
            if refreshed is not None:
                done.append(refreshed)
    return done
