"""Dedicated ingest-job worker process (poll + SKIP LOCKED)."""

from __future__ import annotations

import logging
import signal
import time

from rag_api.config import get_settings
from rag_api.db.session import get_session_factory
from rag_api.ingestion.worker import process_pending_ingest_jobs

logger = logging.getLogger(__name__)

_stop = False


def _handle_signal(signum: int, _frame: object) -> None:
    global _stop
    logger.info("ingest worker received signal %s; shutting down", signum)
    _stop = True


def run_forever() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    settings = get_settings()
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    factory = get_session_factory()
    poll = max(0.2, float(settings.ingest_worker_poll_interval_seconds))
    batch = max(1, int(settings.ingest_worker_batch_size))
    logger.info(
        "ingest worker started poll=%.2fs batch=%s stuck_after=%ss",
        poll,
        batch,
        settings.ingest_job_stuck_after_seconds,
    )

    while not _stop:
        session = factory()
        try:
            done = process_pending_ingest_jobs(session, limit=batch)
            if done:
                logger.info("ingest worker processed %s job(s)", len(done))
        except Exception:  # noqa: BLE001 — keep looping
            logger.exception("ingest worker loop error")
        finally:
            session.close()
        if _stop:
            break
        time.sleep(poll)

    logger.info("ingest worker stopped")


def run() -> None:
    run_forever()


if __name__ == "__main__":
    run()
