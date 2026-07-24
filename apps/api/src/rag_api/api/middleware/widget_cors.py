"""CORS for F12 widget public routes (reflect Origin when whitelisted for tenant)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def _widget_path(path: str) -> bool:
    return path.startswith("/v1/widget/")


class WidgetCorsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _widget_path(request.url.path):
            return await call_next(request)

        # Deferred imports avoid circular import via dependencies.__init__
        from rag_api.services.widget_site_keys import origin_from_headers

        origin_hdr = request.headers.get("origin")
        referer = request.headers.get("referer")
        request_origin = origin_from_headers(origin_hdr, referer)

        if request.method == "OPTIONS":
            if request_origin and _origin_allowed_for_host(request, request_origin):
                return Response(
                    status_code=204,
                    headers=_cors_headers(request_origin),
                )
            return Response(status_code=403)

        response = await call_next(request)
        allowed = getattr(request.state, "widget_allowed_origin", None)
        if allowed:
            for k, v in _cors_headers(allowed).items():
                response.headers[k] = v
        return response


def _cors_headers(origin: str) -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Headers": "Content-Type, X-Site-Key",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Max-Age": "600",
        "Vary": "Origin",
    }


def _origin_allowed_for_host(request: Request, request_origin: str) -> bool:
    from sqlalchemy import select

    from rag_api.api.dependencies.auth import parse_subdomain
    from rag_api.db.models import Tenant
    from rag_api.db.models.tenant import TENANT_STATUS_ACTIVE
    from rag_api.db.models.widget_site_key import STATUS_ACTIVE, WidgetSiteKey
    from rag_api.db.session import get_session_factory

    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or ""
    )
    subdomain = parse_subdomain(host)
    if subdomain is None:
        return False
    factory = get_session_factory()
    with factory() as db:
        tenant = db.scalar(
            select(Tenant).where(Tenant.tenant_name == subdomain)
        )
        if tenant is None or tenant.status != TENANT_STATUS_ACTIVE:
            return False
        rows = db.scalars(
            select(WidgetSiteKey).where(
                WidgetSiteKey.tenant_id == tenant.tenant_id,
                WidgetSiteKey.status == STATUS_ACTIVE,
            )
        ).all()
        for row in rows:
            if request_origin in (row.allowed_origins or []):
                return True
    return False
