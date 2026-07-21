"""Pydantic schemas for F05 conversations API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ConversationOut(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    title: str
    status: Literal["active", "archived"]
    create_at: datetime
    update_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str = Field(min_length=1)
    meta: Optional[dict[str, Any]] = None


class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    tenant_id: UUID
    role: Literal["user", "assistant", "system", "tool", "summary"]
    content: str
    meta: Optional[dict[str, Any]] = None
    agent_run_id: Optional[UUID] = None
    create_at: datetime
    update_at: datetime

    model_config = {"from_attributes": True}


class TurnReply(BaseModel):
    """F06: user message + assistant reply from Agent Loop."""

    user: MessageOut
    assistant: MessageOut
    agent_run_id: UUID
    used_search: bool
    status: Literal["completed", "truncated", "error"]
    conversation_title: Optional[str] = None
