"""F11 public API auth: Bearer rk_live_ + Host tenant + rate limit."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from rag_api.api.dependencies.auth import get_current_tenant
from rag_api.api.dependencies.db import get_db
from rag_api.api.errors import PublicApiError
from rag_api.db.models import Tenant
from rag_api.db.models.api_key import ApiKey
from rag_api.services import api_keys as api_key_svc
from rag_api.services.rate_limit import api_key_limiter


@dataclass(frozen=True)
class PublicApiAuthContext:
    tenant_id: UUID
    api_key_id: UUID
    subdomain: str


def _bearer_secret(authorization: str | None) -> str:
    if not authorization or not authorization.strip():
        raise PublicApiError(401, "unauthorized", "Invalid API key")
    parts = authorization.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise PublicApiError(401, "unauthorized", "Invalid API key")
    return parts[1].strip()


def require_public_api_key(
    request: Request,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> PublicApiAuthContext:
    secret = _bearer_secret(authorization)
    outcome = api_key_svc.resolve_for_host(
        db,
        host_tenant_id=tenant.tenant_id,
        secret=secret,
    )
    if outcome.kind == "unauthorized":
        raise PublicApiError(401, "unauthorized", "Invalid API key")
    if outcome.kind == "forbidden":
        raise PublicApiError(403, "forbidden", "API key does not match tenant")

    row: ApiKey = outcome.api_key  # type: ignore[assignment]
    if not api_key_limiter.allow(row.id):
        raise PublicApiError(429, "rate_limited", "Rate limit exceeded")

    api_key_svc.touch_last_used(db, row)

    return PublicApiAuthContext(
        tenant_id=tenant.tenant_id,
        api_key_id=row.id,
        subdomain=tenant.tenant_name,
    )
