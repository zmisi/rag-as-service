"""F05 conversation routes."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from rag_api.api.dependencies import AuthContext, require_tenant_member
from rag_api.api.schemas.conversations import (
    ConversationCreate,
    ConversationOut,
    ConversationUpdate,
    MessageCreate,
    MessageOut,
)
from rag_api.db.session import get_db
from rag_api.services import conversations as conv_svc

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    body: ConversationCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> ConversationOut:
    conv = conv_svc.create_conversation(
        db, tenant_id=auth.tenant_id, user_id=auth.user_id, title=body.title
    )
    return ConversationOut.model_validate(conv)


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    status_filter: Literal["active", "archived"] = Query(default="active", alias="status"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> list[ConversationOut]:
    items = conv_svc.list_conversations(
        db, tenant_id=auth.tenant_id, user_id=auth.user_id, status=status_filter
    )
    return [ConversationOut.model_validate(c) for c in items]


@router.post("/{conversation_id}/archive", response_model=ConversationOut)
def archive_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> ConversationOut:
    conv = conv_svc.archive_conversation(
        db,
        conversation_id=conversation_id,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
    )
    return ConversationOut.model_validate(conv)


@router.post("/{conversation_id}/unarchive", response_model=ConversationOut)
def unarchive_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> ConversationOut:
    conv = conv_svc.unarchive_conversation(
        db,
        conversation_id=conversation_id,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
    )
    return ConversationOut.model_validate(conv)


@router.patch("/{conversation_id}", response_model=ConversationOut)
def update_conversation(
    conversation_id: UUID,
    body: ConversationUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> ConversationOut:
    conv = conv_svc.rename_conversation(
        db,
        conversation_id=conversation_id,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        title=body.title,
    )
    return ConversationOut.model_validate(conv)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> Response:
    conv_svc.soft_delete_conversation(
        db,
        conversation_id=conversation_id,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> list[MessageOut]:
    messages = conv_svc.list_messages(
        db,
        conversation_id=conversation_id,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
    )
    return [MessageOut.model_validate(m) for m in messages]


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
def post_message(
    conversation_id: UUID,
    body: MessageCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
) -> MessageOut:
    msg = conv_svc.add_message(
        db,
        conversation_id=conversation_id,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        role=body.role,
        content=body.content,
        meta=body.meta,
    )
    return MessageOut.model_validate(msg)
