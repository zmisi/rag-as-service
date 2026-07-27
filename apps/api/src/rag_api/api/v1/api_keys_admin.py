"""F11 Admin: API Key create / list / revoke (member cookie)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from rag_api.api.dependencies import AuthContext, get_db, require_tenant_member
from rag_api.api.schemas.public_api import ApiKeyCreate, ApiKeyCreatedOut, ApiKeyOut
from rag_api.services import api_keys as api_key_svc

router = APIRouter(prefix="/admin/api-keys", tags=["api-keys-admin"])


@router.post("", response_model=ApiKeyCreatedOut, status_code=status.HTTP_201_CREATED)
def create_api_key(
    body: ApiKeyCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> ApiKeyCreatedOut:
    row, secret = api_key_svc.create_api_key(
        db,
        tenant_id=auth.tenant_id,
        name=body.name,
    )
    return ApiKeyCreatedOut(
        id=row.id,
        name=row.name,
        key_prefix=row.key_prefix,
        status=row.status,  # type: ignore[arg-type]
        secret=secret,
        create_at=row.create_at,
    )


@router.get("", response_model=list[ApiKeyOut])
def list_api_keys(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> list[ApiKeyOut]:
    rows = api_key_svc.list_api_keys(db, tenant_id=auth.tenant_id)
    return [ApiKeyOut.model_validate(r) for r in rows]


@router.post("/{api_key_id}/revoke", response_model=ApiKeyOut)
def revoke_api_key(
    api_key_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> ApiKeyOut:
    row = api_key_svc.revoke_api_key(
        db, tenant_id=auth.tenant_id, api_key_id=api_key_id
    )
    return ApiKeyOut.model_validate(row)
