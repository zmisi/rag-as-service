"""P3-F04 Admin Debug request/response schemas."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from rag_api.api.schemas.conversations import TurnReply


class DebugSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class DebugSearchHit(BaseModel):
    document_id: str
    chunk_id: str
    section_id: str = ""
    path: str = ""
    content: str
    score: float = 0.0


class DebugSearchResponse(BaseModel):
    hits: list[DebugSearchHit]


class DebugChatRequest(BaseModel):
    """Portal-equivalent user turn; optional conversation_id for draft first send."""

    content: str = Field(min_length=1)
    conversation_id: Optional[UUID] = None


class DebugLlmCall(BaseModel):
    step: int
    request_summary: dict[str, Any]
    response_summary: dict[str, Any]


class AgentDebugPayload(BaseModel):
    context_messages: list[dict[str, Any]]
    top_k_hits: list[DebugSearchHit]
    history: list[dict[str, Any]]
    llm_calls: list[DebugLlmCall]


class DebugChatResponse(TurnReply):
    """Portal TurnReply fields plus debug panel payload."""

    debug: AgentDebugPayload
