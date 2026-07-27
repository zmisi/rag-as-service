from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from rag_api.api.errors import (
    PublicApiError,
    public_api_error_handler,
    public_api_validation_handler,
)
from rag_api.api.middleware.widget_cors import WidgetCorsMiddleware
from rag_api.api.v1 import api_router
from rag_api.api.v1.auth import router as auth_router
from rag_api.api.v1.public_api import router as public_api_router
from rag_api.config import get_settings


def create_app(lifespan=None) -> FastAPI:
    """Build the FastAPI application with routers and health endpoints."""
    settings = get_settings()
    app = FastAPI(
        title="rag-as-service API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(WidgetCorsMiddleware)
    app.add_exception_handler(PublicApiError, public_api_error_handler)
    app.add_exception_handler(RequestValidationError, public_api_validation_handler)

    app.include_router(auth_router)
    # F11 public API: /api/v1/search, /api/v1/chat
    app.include_router(public_api_router)
    # F05 conversations: /v1/conversations (via /backend/v1/*)
    app.include_router(api_router, prefix="/v1")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "apex_host": settings.apex_host}

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
