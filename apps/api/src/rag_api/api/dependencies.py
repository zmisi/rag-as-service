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
    x_forwarded_host: str | None = Header(default=None, alias="X-Forwarded-Host"),
) -> Tenant:
    # Prefer X-Forwarded-Host so Next /backend rewrites still carry the browser Host.
    raw_host = x_forwarded_host or host or request.headers.get("host")
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
    x_test_user_id: str | None = Header(default=None, alias="X-Test-User-Id"),
) -> User:
    """F02 placeholder: cookie auth not wired.

    When AUTH_STUB_ENABLED=true, accept X-Test-User-Id for local UI / tests.
    Tests may still override this dependency.
    """
    from rag_api.config import get_settings

    if get_settings().auth_stub_enabled:
        if not x_test_user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            user_id = UUID(x_test_user_id)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid user id") from exc
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="Unknown user")
        return user

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
