from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from rag_api.api.v1 import api_router
from rag_api.config import get_settings
from rag_api.db import run_migrations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    if settings.auto_migrate:
        run_migrations(database_url=settings.database_url)
    else:
        logger.info("AUTO_MIGRATE=false; skipping Alembic upgrade")
    yield


app = FastAPI(title="rag-as-service", lifespan=lifespan)
app.include_router(api_router, prefix="/v1")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


def run() -> None:
    uvicorn.run("rag_api.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
