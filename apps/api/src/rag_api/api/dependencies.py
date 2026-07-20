"""FastAPI dependencies: DB session, tenant from Host, user auth stub."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_api.db.models import Tenant, TenantMember, User
from rag_api.db.session import get_db

_HOST_SUBDOMAIN_RE = re.compile(
    r"^(?P<subdomain>[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?)\.lxzxai\.com(?::\d+)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AuthContext:
    user_id: UUID
    tenant_id: UUID
    email: str
    subdomain: str


def parse_subdomain(host: str | None) -> str | None:
    if not host:
        return None
    host = host.split(",")[0].strip().lower()
    match = _HOST_SUBDOMAIN_RE.match(host)
    if not match:
        return None
    return match.group("subdomain").lower()


def get_current_tenant(
    request: Request,
    db: Session = Depends(get_db),
    host: str | None = Header(default=None, alias="Host"),
) -> Tenant:
    raw_host = host or request.headers.get("host")
    subdomain = parse_subdomain(raw_host)
    if subdomain is None:
        raise HTTPException(status_code=404, detail="Unknown host")
    tenant = db.scalar(select(Tenant).where(Tenant.subdomain == subdomain))
    if tenant is None:
        raise HTTPException(status_code=404, detail="Unknown tenant")
    return tenant


def get_current_user(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
) -> User:
    """F02 placeholder: cookie auth not wired; tests override this dependency."""
    raise HTTPException(status_code=401, detail="Not authenticated")


def require_tenant_member(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
) -> AuthContext:
    member = db.scalar(
        select(TenantMember).where(
            TenantMember.tenant_id == tenant.id,
            TenantMember.user_id == user.id,
        )
    )
    if member is None:
        raise HTTPException(status_code=403, detail="Not a tenant member")
    return AuthContext(
        user_id=user.id,
        tenant_id=tenant.id,
        email=user.email,
        subdomain=tenant.subdomain,
    )
