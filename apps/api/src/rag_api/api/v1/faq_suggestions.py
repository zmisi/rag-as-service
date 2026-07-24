"""F13 Portal FAQ suggestion routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from rag_api.api.dependencies import AuthContext, get_db, require_tenant_member
from rag_api.api.schemas.faq_suggestions import FaqClickOut, FaqSuggestionOut
from rag_api.services import faq_suggestions as faq_svc

router = APIRouter(prefix="/portal/faq-suggestions", tags=["portal-faq"])


@router.get("", response_model=list[FaqSuggestionOut])
def get_faq_suggestions(
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> list[FaqSuggestionOut]:
    items = faq_svc.list_faq_suggestions(db, tenant_id=auth.tenant_id, offset=offset)
    return [
        FaqSuggestionOut(
            document_group_id=i.document_group_id,
            document_id=i.document_id,
            question=i.question,
            click_count=i.click_count,
            hot=i.hot,
        )
        for i in items
    ]


@router.post("/{document_group_id}/click", response_model=FaqClickOut)
def click_faq_suggestion(
    document_group_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> FaqClickOut:
    item = faq_svc.click_faq_suggestion(
        db, tenant_id=auth.tenant_id, document_group_id=document_group_id
    )
    return FaqClickOut(
        document_group_id=item.document_group_id,
        document_id=item.document_id,
        question=item.question,
        click_count=item.click_count,
    )
