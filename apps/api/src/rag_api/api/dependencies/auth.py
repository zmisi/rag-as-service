"""Auth and tenant membership dependencies."""

from __future__ import annotations

import hmac
import re
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_api.api.dependencies.db import get_db
from rag_api.config import Settings, get_settings
from rag_api.db.models import Tenant, TenantMember, User
from rag_api.services.session_service import SessionService

_HOST_SUBDOMAIN_RE = re.compile(
    r"^(?P<subdomain>[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?)\.lxzxai\.com(?::\d+)?$",
    re.IGNORECASE,
)
_PROXY_SECRET_HEADER = "X-Rag-Proxy-Secret"


@dataclass(frozen=True)
class AuthContext:
    user_id: UUID
    tenant_id: UUID
    email: str
    subdomain: str


def hostname_from_host_header(host_header: str) -> str:
    return host_header.split(":")[0].lower()


def parse_subdomain(host: str | None) -> str | None:
    if not host:
        return None
    host = host.split(",")[0].strip().lower()
    match = _HOST_SUBDOMAIN_RE.match(host)
    if not match:
        return None
    return match.group("subdomain").lower()


def is_public_hostname(host_header: str, settings: Settings) -> bool:
    hostname = hostname_from_host_header(host_header.split(",")[0].strip())
    if hostname == settings.apex_host.lower():
        return True
    return parse_subdomain(host_header) is not None


def _proxy_secret_ok(request: Request, settings: Settings) -> bool:
    expected = (settings.proxy_shared_secret or "").strip()
    if not expected:
        return False
    provided = (request.headers.get(_PROXY_SECRET_HEADER) or "").strip()
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)


def resolve_public_host(
    request: Request,
    *,
    host: str | None,
    x_forwarded_host: str | None,
    settings: Settings,
) -> str:
    """Resolve browser-facing Host.

    Prefer a public ``Host`` (apex / tenant subdomain). Only trust
    ``X-Forwarded-Host`` when the request carries a matching proxy shared secret
    (set by Next BFF / Caddy — never by the browser).
    """
    host_val = (host or request.headers.get("host") or "").split(",")[0].strip()
    if host_val and is_public_hostname(host_val, settings):
        return host_val

    xfh = (x_forwarded_host or "").split(",")[0].strip()
    if xfh and _proxy_secret_ok(request, settings):
        return xfh

    return host_val


def _raw_host(
    request: Request,
    host: str | None,
    x_forwarded_host: str | None,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    return resolve_public_host(
        request,
        host=host,
        x_forwarded_host=x_forwarded_host,
        settings=settings,
    )


def require_known_host(
    request: Request,
    settings: Settings = Depends(get_settings),
    host: str | None = Header(default=None, alias="Host"),
    x_forwarded_host: str | None = Header(default=None, alias="X-Forwarded-Host"),
) -> None:
    host_header = _raw_host(request, host, x_forwarded_host, settings)
    hostname = hostname_from_host_header(host_header.split(",")[0].strip())
    if hostname == settings.apex_host.lower():
        return
    if parse_subdomain(host_header) is not None:
        return
    raise HTTPException(status_code=404, detail="not found")


def get_current_tenant(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    host: str | None = Header(default=None, alias="Host"),
    x_forwarded_host: str | None = Header(default=None, alias="X-Forwarded-Host"),
) -> Tenant:
    from rag_api.db.models.tenant import TENANT_STATUS_ACTIVE

    raw_host = _raw_host(request, host, x_forwarded_host, settings)
    subdomain = parse_subdomain(raw_host)
    if subdomain is None:
        raise HTTPException(status_code=404, detail="Unknown host")
    tenant = db.scalar(select(Tenant).where(Tenant.tenant_name == subdomain))
    if tenant is None or tenant.status != TENANT_STATUS_ACTIVE:
        raise HTTPException(status_code=404, detail="Unknown tenant")
    return tenant


def _session_user_from_cookie(
    request: Request,
    db: Session,
    settings: Settings,
) -> User:
    from rag_api.db.models.user import USER_ACTIVE

    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    service = SessionService(db, settings)
    validated = service.validate_session(token)
    if validated is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if validated.user.active != USER_ACTIVE:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if service.maybe_slide_expiry(validated.session):
        db.commit()

    return validated.user


def get_session_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    return _session_user_from_cookie(request, db, settings)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    x_test_user_id: str | None = Header(default=None, alias="X-Test-User-Id"),
) -> User:
    from rag_api.db.models.user import USER_ACTIVE

    token = request.cookies.get(settings.session_cookie_name)
    if token:
        validated = SessionService(db, settings).validate_session(token)
        if validated is not None:
            if validated.user.active != USER_ACTIVE:
                raise HTTPException(status_code=401, detail="Not authenticated")
            service = SessionService(db, settings)
            if service.maybe_slide_expiry(validated.session):
                db.commit()
            return validated.user

    if settings.auth_stub_enabled:
        if not x_test_user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            user_id = UUID(x_test_user_id)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid user id") from exc
        user = db.get(User, user_id)
        if user is None or user.active != USER_ACTIVE:
            raise HTTPException(status_code=401, detail="Unknown user")
        return user

    raise HTTPException(status_code=401, detail="Not authenticated")


def require_tenant_member(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(get_current_user),
) -> AuthContext:
    from rag_api.db.models.tenant_member import MEMBER_ACTIVE

    member = db.scalar(
        select(TenantMember).where(
            TenantMember.tenant_id == tenant.tenant_id,
            TenantMember.user_id == user.user_id,
        )
    )
    if member is None:
        raise HTTPException(status_code=403, detail="Not a tenant member")
    if member.active != MEMBER_ACTIVE:
        raise HTTPException(status_code=403, detail="Not a tenant member")
    return AuthContext(
        user_id=user.user_id,
        tenant_id=tenant.tenant_id,
        email=user.email,
        subdomain=tenant.tenant_name,
    )
