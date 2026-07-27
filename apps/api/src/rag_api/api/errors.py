"""F11 public API error envelope: { "error": { "code", "message" } }."""

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class PublicApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def public_api_error_response(exc: PublicApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


async def public_api_error_handler(
    _request: Request,
    exc: PublicApiError,
) -> JSONResponse:
    return public_api_error_response(exc)


def _is_public_api_path(path: str) -> bool:
    return path in ("/api/v1/search", "/api/v1/chat")


async def public_api_validation_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    if _is_public_api_path(request.url.path):
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Invalid request body",
                }
            },
        )
    # Fall back to FastAPI-style detail for other routes
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )
