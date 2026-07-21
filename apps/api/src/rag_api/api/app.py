from fastapi import FastAPI

from rag_api.api.v1 import api_router
from rag_api.api.v1.auth import router as auth_router
from rag_api.config import get_settings


def create_app(lifespan=None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="rag-as-service API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.include_router(auth_router)
    # F05 conversations: /v1/conversations (via /backend/v1/*)
    app.include_router(api_router, prefix="/v1")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "apex_host": settings.apex_host}

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
