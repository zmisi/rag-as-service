from fastapi import Depends, HTTPException, Request

from rag_api.api.dependencies.auth import resolve_public_host
from rag_api.config import Settings, get_settings


def require_apex_host(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    host_header = resolve_public_host(
        request,
        host=request.headers.get("host"),
        x_forwarded_host=request.headers.get("x-forwarded-host"),
        settings=settings,
    )
    host = host_header.split(":")[0].lower()
    if host != settings.apex_host.lower():
        raise HTTPException(status_code=404, detail="not found")
