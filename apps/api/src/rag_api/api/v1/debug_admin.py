"""P3-F04 Admin Debug: search-only + Agent debug (member cookie)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from rag_api.agent.service import run_user_turn
from rag_api.api.dependencies import (
    AuthContext,
    get_db,
    get_knowledge_searcher,
    get_llm_client,
    require_tenant_member,
)
from rag_api.api.schemas.conversations import MessageOut
from rag_api.api.schemas.debug import (
    DebugChatRequest,
    DebugChatResponse,
    DebugSearchHit,
    DebugSearchRequest,
    DebugSearchResponse,
)
from rag_api.clients.llm import LlmClient
from rag_api.config import Settings, get_settings
from rag_api.ingestion.search import KnowledgeSearcher
from rag_api.services import conversations as conv_svc
from rag_api.services.debug_payload import build_agent_debug_payload

router = APIRouter(prefix="/admin/debug", tags=["admin-debug"])


def require_admin_debug_enabled(
    settings: Settings = Depends(get_settings),
) -> Settings:
    """Return settings when Admin Debug is enabled; otherwise HTTP 404."""
    if not settings.enable_admin_debug:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )
    return settings


@router.get("")
def debug_probe(
    _auth: AuthContext = Depends(require_tenant_member),
    _settings: Settings = Depends(require_admin_debug_enabled),
) -> dict[str, bool]:
    """Lightweight probe for the Admin Debug UI (404 when disabled)."""
    return {"enabled": True}


@router.post("/search", response_model=DebugSearchResponse)
def debug_search(
    body: DebugSearchRequest,
    auth: AuthContext = Depends(require_tenant_member),
    _settings: Settings = Depends(require_admin_debug_enabled),
    searcher: KnowledgeSearcher = Depends(get_knowledge_searcher),
) -> DebugSearchResponse:
    """Search-only: same KnowledgeSearcher.search as Portal/public; zero LLM."""
    hits = searcher.search(auth.tenant_id, body.query, top_k=body.top_k)
    return DebugSearchResponse(
        hits=[
            DebugSearchHit(
                document_id=h.document_id,
                chunk_id=h.chunk_id,
                section_id=h.section_id,
                path=h.path,
                content=h.content,
                score=h.score,
            )
            for h in hits
        ]
    )


@router.post("/chat", response_model=DebugChatResponse, status_code=status.HTTP_201_CREATED)
def debug_chat(
    body: DebugChatRequest,
    auth: AuthContext = Depends(require_tenant_member),
    settings: Settings = Depends(require_admin_debug_enabled),
    db: Session = Depends(get_db),
    llm: LlmClient = Depends(get_llm_client),
    searcher: KnowledgeSearcher = Depends(get_knowledge_searcher),
) -> DebugChatResponse:
    """Agent debug: Portal resolve + run_user_turn, plus debug panel payload."""
    conversation_id = conv_svc.resolve_conversation_for_portal_message(
        db,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        conversation_id=body.conversation_id,
        content=body.content,
    )
    turn = run_user_turn(
        db,
        conversation_id=conversation_id,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        content=body.content,
        llm=llm,
        searcher=searcher,
    )
    messages = conv_svc.list_messages(
        db,
        conversation_id=conversation_id,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
    )
    history_for_debug = [m for m in messages if m.id != turn.assistant.id]
    debug = build_agent_debug_payload(
        history=history_for_debug,
        user_content=body.content,
        loop=turn.loop,
        settings=settings,
    )
    return DebugChatResponse(
        user=MessageOut.model_validate(turn.user),
        assistant=MessageOut.model_validate(turn.assistant),
        agent_run_id=turn.agent_run.id,
        used_search=turn.agent_run.used_search,
        status=turn.agent_run.status,  # type: ignore[arg-type]
        conversation_title=turn.conversation_title,
        conversation_id=conversation_id,
        debug=debug,
    )
