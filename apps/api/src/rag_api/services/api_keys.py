"""F11 tenant public API keys (rk_live_): create / list / revoke / resolve."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_api.db.models.api_key import (
    SECRET_PREFIX,
    STATUS_ACTIVE,
    STATUS_REVOKED,
    ApiKey,
)

_PREFIX_RANDOM_LEN = 8
_SECRET_RANDOM_BYTES = 24


@dataclass(frozen=True)
class ResolveOutcome:
    """Result of Bearer secret lookup against Host tenant."""

    kind: str  # ok | unauthorized | forbidden
    api_key: ApiKey | None = None


def generate_secret() -> tuple[str, str]:
    """Return (full_secret, key_prefix). Prefix = rk_live_ + first 8 of random part."""
    random_part = secrets.token_urlsafe(_SECRET_RANDOM_BYTES)
    secret = f"{SECRET_PREFIX}{random_part}"
    key_prefix = f"{SECRET_PREFIX}{random_part[:_PREFIX_RANDOM_LEN]}"
    return secret, key_prefix


def hash_api_key_secret(secret: str) -> str:
    """Deterministic irreversible hash for lookup (high-entropy secret)."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def create_api_key(
    db: Session,
    *,
    tenant_id: UUID,
    name: str | None = None,
) -> tuple[ApiKey, str]:
    secret, key_prefix = generate_secret()
    cleaned = name.strip() if name and name.strip() else None
    row = ApiKey(
        tenant_id=tenant_id,
        name=cleaned,
        key_prefix=key_prefix,
        key_hash=hash_api_key_secret(secret),
        status=STATUS_ACTIVE,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, secret


def list_api_keys(db: Session, *, tenant_id: UUID) -> list[ApiKey]:
    stmt = (
        select(ApiKey)
        .where(ApiKey.tenant_id == tenant_id)
        .order_by(ApiKey.create_at.desc())
    )
    return list(db.scalars(stmt).all())


def get_api_key_for_tenant(
    db: Session,
    *,
    tenant_id: UUID,
    api_key_id: UUID,
) -> ApiKey:
    row = db.scalar(
        select(ApiKey).where(
            ApiKey.id == api_key_id,
            ApiKey.tenant_id == tenant_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found")
    return row


def revoke_api_key(
    db: Session,
    *,
    tenant_id: UUID,
    api_key_id: UUID,
) -> ApiKey:
    row = get_api_key_for_tenant(db, tenant_id=tenant_id, api_key_id=api_key_id)
    row.status = STATUS_REVOKED
    db.commit()
    db.refresh(row)
    return row


def find_api_key_by_secret(db: Session, *, secret: str) -> ApiKey | None:
    if not secret.startswith(SECRET_PREFIX):
        return None
    key_hash = hash_api_key_secret(secret)
    return db.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash))


def touch_last_used(db: Session, row: ApiKey) -> None:
    row.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()


def resolve_for_host(
    db: Session,
    *,
    host_tenant_id: UUID,
    secret: str,
) -> ResolveOutcome:
    """Map Bearer secret + Host tenant to ok / unauthorized / forbidden."""
    stripped = secret.strip()
    if not stripped.startswith(SECRET_PREFIX):
        return ResolveOutcome(kind="unauthorized")
    row = find_api_key_by_secret(db, secret=stripped)
    if row is None or row.status != STATUS_ACTIVE:
        return ResolveOutcome(kind="unauthorized")
    if row.tenant_id != host_tenant_id:
        return ResolveOutcome(kind="forbidden", api_key=row)
    return ResolveOutcome(kind="ok", api_key=row)
