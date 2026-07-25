from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn

from rag_api.api import create_app
from rag_api.config import get_settings
from rag_api.db import run_migrations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app):
    """Run Alembic migrations on startup when ``AUTO_MIGRATE`` is enabled."""
    settings = get_settings()
    if settings.auto_migrate:
        run_migrations(database_url=settings.database_url)
    else:
        logger.info("AUTO_MIGRATE=false; skipping Alembic upgrade")
    yield


app = create_app(lifespan=lifespan)


def run() -> None:
    """Start uvicorn with reload using configured host and port."""
    settings = get_settings()
    uvicorn.run(
        "rag_api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


if __name__ == "__main__":
    run()
