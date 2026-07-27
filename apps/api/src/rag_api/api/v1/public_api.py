"""F11 public tenant API: POST /api/v1/search and /api/v1/chat."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from rag_api.agent.service import run_user_turn
from rag_api.api.dependencies import get_db, get_knowledge_searcher, get_llm_client
from rag_api.api.dependencies.public_api import (
    PublicApiAuthContext,
    require_public_api_key,
)
from rag_api.api.schemas.public_api import (
    PublicChatRequest,
    PublicChatResponse,
    PublicSearchHit,
    PublicSearchRequest,
    PublicSearchResponse,
)
from rag_api.clients.llm import LlmClient
from rag_api.indexing.search import KnowledgeSearcher
from rag_api.services import conversations as conv_svc

router = APIRouter(prefix="/api/v1", tags=["public-api"])


@router.post("/search", response_model=PublicSearchResponse)
def public_search(
    body: PublicSearchRequest,
    db: Session = Depends(get_db),
    auth: PublicApiAuthContext = Depends(require_public_api_key),
    searcher: KnowledgeSearcher = Depends(get_knowledge_searcher),
) -> PublicSearchResponse:
    hits = searcher.search(auth.tenant_id, body.query, top_k=body.top_k)
    return PublicSearchResponse(
        hits=[
            PublicSearchHit(
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


@router.post("/chat", response_model=PublicChatResponse)
def public_chat(
    body: PublicChatRequest,
    db: Session = Depends(get_db),
    auth: PublicApiAuthContext = Depends(require_public_api_key),
    llm: LlmClient = Depends(get_llm_client),
    searcher: KnowledgeSearcher = Depends(get_knowledge_searcher),
) -> PublicChatResponse:
    conversation_id = conv_svc.resolve_conversation_for_api_key_message(
        db,
        tenant_id=auth.tenant_id,
        api_key_id=auth.api_key_id,
        conversation_id=body.conversation_id,
        content=body.message,
    )
    turn = run_user_turn(
        db,
        conversation_id=conversation_id,
        tenant_id=auth.tenant_id,
        content=body.message,
        llm=llm,
        searcher=searcher,
        api_key_id=auth.api_key_id,
    )
    return PublicChatResponse(
        conversation_id=conversation_id,
        message=turn.assistant.content,
        used_search=turn.loop.used_search,
    )
