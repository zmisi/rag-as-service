"""Persistence for ingest_jobs queue (claim / reclaim / status)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from rag_api.config import get_settings
from rag_api.db.models import IngestJob


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class IngestJobRepository:
    """Status transitions and worker claim/reclaim for ingest jobs."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, job_id: UUID) -> IngestJob | None:
        """Load an ingest job by id, or None if missing."""
        return self._session.get(IngestJob, job_id)

    def mark_running(self, job: IngestJob, *, increment_attempt: bool = True) -> None:
        """Set job to running, optionally bump attempt count, and clear prior error."""
        job.status = "running"
        job.started_at = _now()
        if increment_attempt:
            job.attempt_count = int(job.attempt_count or 0) + 1
        job.error = None
        job.finished_at = None

    def mark_succeeded(
        self,
        job: IngestJob,
        *,
        error: str | None = None,
    ) -> None:
        """Mark job succeeded and record finish time."""
        job.status = "succeeded"
        job.finished_at = _now()
        job.error = error

    def mark_failed(self, job: IngestJob, *, error: str) -> None:
        """Mark job failed and store a truncated error message."""
        job.status = "failed"
        job.finished_at = _now()
        job.error = error[:2000]

    def reclaim_stuck(
        self,
        *,
        older_than_seconds: int | None = None,
        tenant_id: UUID | None = None,
    ) -> int:
        """Reset long-running jobs back to pending so workers can retry."""
        settings = get_settings()
        seconds = (
            older_than_seconds
            if older_than_seconds is not None
            else settings.ingest_job_stuck_after_seconds
        )
        params: dict[str, object] = {"seconds": int(seconds)}
        tenant_clause = ""
        if tenant_id is not None:
            tenant_clause = "AND tenant_id = CAST(:tenant_id AS uuid)"
            params["tenant_id"] = str(tenant_id)
        result = self._session.execute(
            text(
                f"""
                UPDATE rag_service.ingest_jobs
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
        self._session.commit()
        return int(result.rowcount or 0)

    def claim_pending(
        self,
        *,
        limit: int = 20,
        tenant_id: UUID | None = None,
    ) -> list[UUID]:
        """Claim pending jobs with ``FOR UPDATE SKIP LOCKED`` (multi-worker safe)."""
        self.reclaim_stuck(tenant_id=tenant_id)

        params: dict[str, object] = {"limit": int(limit)}
        tenant_clause = ""
        if tenant_id is not None:
            tenant_clause = "AND tenant_id = CAST(:tenant_id AS uuid)"
            params["tenant_id"] = str(tenant_id)

        rows = self._session.execute(
            text(
                f"""
                SELECT id
                FROM rag_service.ingest_jobs
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
            self._session.commit()
            return []

        for job_id in ids:
            job = self._session.get(IngestJob, job_id)
            if job is None or job.status != "pending":
                continue
            self.mark_running(job, increment_attempt=True)
        self._session.commit()
        return ids
