"""Conversation / message business rules (F05)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rag_api.db.models import Conversation, Message

DEFAULT_TITLE = "新会话"
AUTO_TITLE_MAX_LEN = 60


def derive_title_from_message(content: str, max_len: int = AUTO_TITLE_MAX_LEN) -> str:
    """Summarize first user message as conversation title (F05)."""
    text = " ".join(content.strip().split())
    if not text:
        return DEFAULT_TITLE
    if len(text) <= max_len:
        return text
    trimmed = text[: max_len - 1].rstrip()
    return f"{trimmed}…"


def maybe_set_title_from_first_message(
    db: Session,
    *,
    conversation_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    user_content: str,
) -> str | None:
    """When title is still default, set it from the first user message."""
    conv = get_owned_conversation(
        db, conversation_id=conversation_id, tenant_id=tenant_id, user_id=user_id
    )
    if conv.title != DEFAULT_TITLE:
        return None
    user_count = db.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.tenant_id == tenant_id,
            Message.role == "user",
        )
    )
    if user_count != 1:
        return None
    conv.title = derive_title_from_message(user_content)
    db.commit()
    db.refresh(conv)
    return conv.title


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


def resolve_conversation_for_portal_message(
    db: Session,
    *,
    tenant_id: UUID,
    user_id: UUID,
    conversation_id: UUID | None,
    content: str,
) -> UUID:
    """F14: use existing conversation or create one for draft first send."""
    if conversation_id is not None:
        get_owned_conversation(
            db,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        return conversation_id
    conv = create_conversation(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        title=derive_title_from_message(content),
    )
    return conv.id


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


def rename_conversation(
    db: Session,
    *,
    conversation_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    title: str,
) -> Conversation:
    conv = get_owned_conversation(
        db, conversation_id=conversation_id, tenant_id=tenant_id, user_id=user_id
    )
    cleaned = title.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Title required")
    conv.title = cleaned
    db.commit()
    db.refresh(conv)
    return conv


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
