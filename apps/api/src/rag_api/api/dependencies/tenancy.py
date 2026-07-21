from fastapi import Depends, HTTPException, Request

from rag_api.config import Settings, get_settings


def require_apex_host(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    # When requests are proxied (e.g. Next.js `/backend/*` rewrite),
    # the `Host` header may become the upstream host (api:8000). In that case
    # we prefer `X-Forwarded-Host` which typically carries the original host.
    x_forwarded_host = request.headers.get("x-forwarded-host") or ""
    if x_forwarded_host:
        # It can be a comma-separated list, take the first hop.
        x_forwarded_host = x_forwarded_host.split(",")[0].strip()
        host_header = x_forwarded_host
    else:
        host_header = request.headers.get("host", "")

    host = host_header.split(":")[0].lower()
    if host != settings.apex_host.lower():
        raise HTTPException(status_code=404, detail="not found")
