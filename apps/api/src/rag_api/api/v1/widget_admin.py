"""F12 Admin: widget site key CRUD + snippet."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from rag_api.api.dependencies import AuthContext, get_db, require_tenant_member
from rag_api.api.schemas.widget import (
    WidgetSiteKeyCreate,
    WidgetSiteKeyOut,
    WidgetSiteKeyUpdate,
    WidgetSnippetOut,
)
from rag_api.config import Settings, get_settings
from rag_api.services import widget_site_keys as site_key_svc

router = APIRouter(prefix="/admin/widget-site-keys", tags=["widget-admin"])


@router.post("", response_model=WidgetSiteKeyOut, status_code=status.HTTP_201_CREATED)
def create_widget_site_key(
    body: WidgetSiteKeyCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> WidgetSiteKeyOut:
    row = site_key_svc.create_site_key(
        db,
        tenant_id=auth.tenant_id,
        allowed_origins=body.allowed_origins,
        name=body.name,
    )
    return WidgetSiteKeyOut.model_validate(row)


@router.get("", response_model=list[WidgetSiteKeyOut])
def list_widget_site_keys(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> list[WidgetSiteKeyOut]:
    rows = site_key_svc.list_site_keys(db, tenant_id=auth.tenant_id)
    return [WidgetSiteKeyOut.model_validate(r) for r in rows]


@router.patch("/{site_key_id}", response_model=WidgetSiteKeyOut)
def update_widget_site_key(
    site_key_id: UUID,
    body: WidgetSiteKeyUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> WidgetSiteKeyOut:
    row = site_key_svc.update_site_key(
        db,
        tenant_id=auth.tenant_id,
        site_key_id=site_key_id,
        allowed_origins=body.allowed_origins,
        name=body.name,
        clear_name=body.clear_name,
    )
    return WidgetSiteKeyOut.model_validate(row)


@router.post("/{site_key_id}/revoke", response_model=WidgetSiteKeyOut)
def revoke_widget_site_key(
    site_key_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> WidgetSiteKeyOut:
    row = site_key_svc.revoke_site_key(
        db, tenant_id=auth.tenant_id, site_key_id=site_key_id
    )
    return WidgetSiteKeyOut.model_validate(row)


@router.get("/{site_key_id}/snippet", response_model=WidgetSnippetOut)
def get_widget_snippet(
    site_key_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
    settings: Settings = Depends(get_settings),
) -> WidgetSnippetOut:
    row = site_key_svc.get_site_key_for_tenant(
        db, tenant_id=auth.tenant_id, site_key_id=site_key_id
    )
    # Prefer request host so local :3000 snippets work.
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
    scheme_host = f"{scheme}://{host}" if host else None
    snippet = site_key_svc.build_snippet(
        subdomain=auth.subdomain,
        public_key=row.public_key,
        apex_host=settings.apex_host,
        scheme_host=scheme_host,
    )
    return WidgetSnippetOut(snippet=snippet, public_key=row.public_key)
