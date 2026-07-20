"""Conversation / message business rules (F05)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_api.db.models import Conversation, Message

DEFAULT_TITLE = "新会话"


def create_conversation(
    db: Session,
    *,
    tenant_id: UUID,
    user_id: UUID,
    title: str | None,
) -> Conversation:
    conv = Conversation(
        tenant_id=tenant_id,
        user_id=user_id,
        title=(title.strip() if title and title.strip() else DEFAULT_TITLE),
        status="active",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def list_conversations(
    db: Session,
    *,
    tenant_id: UUID,
    user_id: UUID,
    status: str,
) -> list[Conversation]:
    if status not in ("active", "archived"):
        raise HTTPException(status_code=422, detail="Invalid status")
    stmt = (
        select(Conversation)
        .where(
            Conversation.tenant_id == tenant_id,
            Conversation.user_id == user_id,
            Conversation.status == status,
            Conversation.deleted_at.is_(None),
        )
        .order_by(Conversation.create_at.desc())
    )
    return list(db.scalars(stmt).all())


def get_owned_conversation(
    db: Session,
    *,
    conversation_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> Conversation:
    conv = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id,
            Conversation.user_id == user_id,
            Conversation.deleted_at.is_(None),
        )
    )
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


def archive_conversation(
    db: Session,
    *,
    conversation_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> Conversation:
    conv = get_owned_conversation(
        db, conversation_id=conversation_id, tenant_id=tenant_id, user_id=user_id
    )
    if conv.status != "active":
        raise HTTPException(status_code=409, detail="Conversation is not active")
    conv.status = "archived"
    db.commit()
    db.refresh(conv)
    return conv


def unarchive_conversation(
    db: Session,
    *,
    conversation_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> Conversation:
    conv = get_owned_conversation(
        db, conversation_id=conversation_id, tenant_id=tenant_id, user_id=user_id
    )
    if conv.status != "archived":
        raise HTTPException(status_code=409, detail="Conversation is not archived")
    conv.status = "active"
    db.commit()
    db.refresh(conv)
    return conv


def soft_delete_conversation(
    db: Session,
    *,
    conversation_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> None:
    conv = get_owned_conversation(
        db, conversation_id=conversation_id, tenant_id=tenant_id, user_id=user_id
    )
    conv.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()


def list_messages(
    db: Session,
    *,
    conversation_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> list[Message]:
    get_owned_conversation(
        db, conversation_id=conversation_id, tenant_id=tenant_id, user_id=user_id
    )
    stmt = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.tenant_id == tenant_id,
        )
        .order_by(Message.create_at.asc())
    )
    return list(db.scalars(stmt).all())


def add_message(
    db: Session,
    *,
    conversation_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    role: str,
    content: str,
    meta: dict | None,
) -> Message:
    conv = get_owned_conversation(
        db, conversation_id=conversation_id, tenant_id=tenant_id, user_id=user_id
    )
    if conv.status != "active":
        raise HTTPException(status_code=409, detail="Cannot add message to archived conversation")
    msg = Message(
        conversation_id=conv.id,
        tenant_id=tenant_id,
        role=role,
        content=content,
        meta=meta,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg
