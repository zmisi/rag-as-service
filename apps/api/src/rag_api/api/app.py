from fastapi import FastAPI

from rag_api.api.v1.auth import router as auth_router
from rag_api.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="rag-as-service API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    app.include_router(auth_router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "apex_host": settings.apex_host}

    return app
