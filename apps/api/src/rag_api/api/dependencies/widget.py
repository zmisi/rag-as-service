"""F12 Embed Widget auth: site key + Origin whitelist + rate limit."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from rag_api.api.dependencies.auth import get_current_tenant
from rag_api.api.dependencies.db import get_db
from rag_api.db.models import Tenant
from rag_api.db.models.widget_site_key import WidgetSiteKey
from rag_api.services import widget_site_keys as site_key_svc
from rag_api.services.rate_limit import widget_site_key_limiter


@dataclass(frozen=True)
class WidgetAuthContext:
    tenant_id: UUID
    site_key_id: UUID
    public_key: str
    subdomain: str
    origin: str


def require_widget_site_key(
    request: Request,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    x_site_key: str | None = Header(default=None, alias="X-Site-Key"),
    origin: str | None = Header(default=None, alias="Origin"),
    referer: str | None = Header(default=None, alias="Referer"),
) -> WidgetAuthContext:
    if not x_site_key or not x_site_key.strip():
        raise HTTPException(status_code=401, detail="Invalid site key")

    site_key: WidgetSiteKey = site_key_svc.resolve_active_site_key(
        db,
        tenant_id=tenant.tenant_id,
        public_key=x_site_key.strip(),
    )
    request_origin = site_key_svc.origin_from_headers(origin, referer)
    allowed = site_key_svc.assert_origin_allowed(site_key, request_origin)

    if not widget_site_key_limiter.allow(site_key.id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Stash for CORS middleware / handlers
    request.state.widget_allowed_origin = allowed

    return WidgetAuthContext(
        tenant_id=tenant.tenant_id,
        site_key_id=site_key.id,
        public_key=site_key.public_key,
        subdomain=tenant.tenant_name,
        origin=allowed,
    )
