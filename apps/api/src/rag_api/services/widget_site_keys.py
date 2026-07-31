"""F12 widget site key CRUD + Origin helpers."""

from __future__ import annotations

import secrets
from urllib.parse import urlparse
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_api.db.models.widget_site_key import (
    STATUS_ACTIVE,
    STATUS_REVOKED,
    WidgetSiteKey,
)


def generate_public_key() -> str:
    return f"pk_{secrets.token_urlsafe(24)}"


def normalize_origin(origin: str) -> str:
    """Normalize to scheme://host[:port] (no path/query/fragment)."""
    raw = origin.strip()
    if not raw:
        raise HTTPException(status_code=422, detail="Empty origin")
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=422, detail=f"Invalid origin: {origin}")
    host = parsed.hostname.lower()
    port = parsed.port
    if port is not None:
        return f"{parsed.scheme}://{host}:{port}"
    return f"{parsed.scheme}://{host}"


def origin_from_headers(origin: str | None, referer: str | None) -> str | None:
    if origin and origin.strip() and origin.strip().lower() != "null":
        try:
            return normalize_origin(origin)
        except HTTPException:
            return None
    if referer and referer.strip():
        try:
            parsed = urlparse(referer.strip())
            if parsed.scheme and parsed.hostname:
                return normalize_origin(
                    f"{parsed.scheme}://{parsed.netloc}"
                )
        except HTTPException:
            return None
    return None


def create_site_key(
    db: Session,
    *,
    tenant_id: UUID,
    allowed_origins: list[str],
    name: str | None = None,
) -> WidgetSiteKey:
    origins = [normalize_origin(o) for o in allowed_origins]
    row = WidgetSiteKey(
        tenant_id=tenant_id,
        public_key=generate_public_key(),
        status=STATUS_ACTIVE,
        allowed_origins=origins,
        name=(name.strip() if name and name.strip() else None),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_site_keys(db: Session, *, tenant_id: UUID) -> list[WidgetSiteKey]:
    stmt = (
        select(WidgetSiteKey)
        .where(WidgetSiteKey.tenant_id == tenant_id)
        .order_by(WidgetSiteKey.create_at.desc())
    )
    return list(db.scalars(stmt).all())


def get_site_key_for_tenant(
    db: Session,
    *,
    tenant_id: UUID,
    site_key_id: UUID,
) -> WidgetSiteKey:
    row = db.scalar(
        select(WidgetSiteKey).where(
            WidgetSiteKey.id == site_key_id,
            WidgetSiteKey.tenant_id == tenant_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Site key not found")
    return row


def update_site_key(
    db: Session,
    *,
    tenant_id: UUID,
    site_key_id: UUID,
    allowed_origins: list[str] | None = None,
    name: str | None = None,
    clear_name: bool = False,
) -> WidgetSiteKey:
    row = get_site_key_for_tenant(db, tenant_id=tenant_id, site_key_id=site_key_id)
    if allowed_origins is not None:
        row.allowed_origins = [normalize_origin(o) for o in allowed_origins]
    if clear_name:
        row.name = None
    elif name is not None:
        row.name = name.strip() or None
    db.commit()
    db.refresh(row)
    return row


def revoke_site_key(
    db: Session,
    *,
    tenant_id: UUID,
    site_key_id: UUID,
) -> WidgetSiteKey:
    row = get_site_key_for_tenant(db, tenant_id=tenant_id, site_key_id=site_key_id)
    row.status = STATUS_REVOKED
    db.commit()
    db.refresh(row)
    return row


def build_snippet(
    *,
    subdomain: str,
    public_key: str,
    apex_host: str,
    scheme_host: str | None = None,
) -> str:
    """Return HTML snippet with widget.js + data-site-key."""
    base = scheme_host or f"https://{subdomain}.{apex_host}"
    return (
        f'<script src="{base}/widget.js"\n'
        f'        data-site-key="{public_key}"\n'
        f"        async></script>"
    )


def resolve_active_site_key(
    db: Session,
    *,
    tenant_id: UUID,
    public_key: str,
) -> WidgetSiteKey:
    row = db.scalar(
        select(WidgetSiteKey).where(
            WidgetSiteKey.public_key == public_key,
            WidgetSiteKey.tenant_id == tenant_id,
        )
    )
    if row is None or row.status != STATUS_ACTIVE:
        raise HTTPException(status_code=401, detail="Invalid site key")
    return row


def assert_origin_allowed(site_key: WidgetSiteKey, request_origin: str | None) -> str:
    if not site_key.allowed_origins:
        raise HTTPException(status_code=403, detail="Origin not allowed")
    if request_origin is None:
        raise HTTPException(status_code=403, detail="Origin not allowed")
    if request_origin not in site_key.allowed_origins:
        raise HTTPException(status_code=403, detail="Origin not allowed")
    return request_origin
