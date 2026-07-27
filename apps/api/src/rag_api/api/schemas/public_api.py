"""F11 API Key admin + public API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: Optional[str] = None


class ApiKeyCreatedOut(BaseModel):
    id: UUID
    name: Optional[str] = None
    key_prefix: str
    status: Literal["active", "revoked"]
    secret: str
    create_at: datetime


class ApiKeyOut(BaseModel):
    id: UUID
    name: Optional[str] = None
    key_prefix: str
    status: Literal["active", "revoked"]
    last_used_at: Optional[datetime] = None
    create_at: datetime

    model_config = {"from_attributes": True}


class PublicSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class PublicSearchHit(BaseModel):
    document_id: str
    chunk_id: str
    section_id: str = ""
    path: str = ""
    content: str
    score: float = 0.0


class PublicSearchResponse(BaseModel):
    hits: list[PublicSearchHit]


class PublicChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: Optional[UUID] = None


class PublicChatResponse(BaseModel):
    conversation_id: UUID
    message: str
    used_search: bool
