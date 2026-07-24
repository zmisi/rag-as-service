"""F12 Embed Widget / site key schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WidgetSiteKeyCreate(BaseModel):
    allowed_origins: list[str] = Field(default_factory=list)
    name: Optional[str] = None


class WidgetSiteKeyUpdate(BaseModel):
    allowed_origins: Optional[list[str]] = None
    name: Optional[str] = None
    clear_name: bool = False


class WidgetSiteKeyOut(BaseModel):
    id: UUID
    tenant_id: UUID
    public_key: str
    status: Literal["active", "revoked"]
    allowed_origins: list[str]
    name: Optional[str] = None
    create_at: datetime
    update_at: datetime

    model_config = {"from_attributes": True}


class WidgetSnippetOut(BaseModel):
    snippet: str
    public_key: str


class WidgetSessionOut(BaseModel):
    conversation_id: UUID


class WidgetChatCreate(BaseModel):
    content: str = Field(min_length=1)
    conversation_id: Optional[UUID] = None
