"""F05 conversation routes (+ F06 Agent Loop on POST user message)."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from rag_api.agent.service import run_user_turn
from rag_api.api.dependencies import (
    AuthContext,
    get_db,
    get_knowledge_searcher,
    get_llm_client,
    require_tenant_member,
)
from rag_api.api.schemas.conversations import (
    ConversationCreate,
    ConversationOut,
    ConversationUpdate,
    MessageCreate,
    MessageOut,
    TurnReply,
)
from rag_api.clients.llm import LlmClient
from rag_api.db.session import get_session_factory
from rag_api.indexing.search import KnowledgeSearcher
from rag_api.services import conversations as conv_svc

router = APIRouter(prefix="/conversations", tags=["conversations"])
_STREAM_EXECUTOR = ThreadPoolExecutor(max_workers=8)


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
    response_model=TurnReply,
    status_code=status.HTTP_201_CREATED,
)
def post_message(
    conversation_id: UUID,
    body: MessageCreate,
    response: Response,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_tenant_member),
    llm: LlmClient = Depends(get_llm_client),
    searcher: KnowledgeSearcher = Depends(get_knowledge_searcher),
) -> TurnReply:
    if body.role != "user":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only role=user triggers Agent Loop; clients must send user messages",
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
    # Expose server-side wall time so the browser can compare RTT vs processing.
    response.headers["Server-Timing"] = f"turn;dur={turn.server_ms:.1f}"
    response.headers["X-Turn-Duration-Ms"] = f"{turn.server_ms:.1f}"
    return _turn_to_reply(turn)


@router.post("/{conversation_id}/messages/stream")
def post_message_stream(
    conversation_id: UUID,
    body: MessageCreate,
    auth: AuthContext = Depends(require_tenant_member),
    llm: LlmClient = Depends(get_llm_client),
    searcher: KnowledgeSearcher = Depends(get_knowledge_searcher),
) -> StreamingResponse:
    if body.role != "user":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only role=user triggers Agent Loop; clients must send user messages",
        )
    session_factory = get_session_factory()

    def _run_turn():
        db = session_factory()
        try:
            return run_user_turn(
                db,
                conversation_id=conversation_id,
                tenant_id=auth.tenant_id,
                user_id=auth.user_id,
                content=body.content,
                llm=llm,
                searcher=searcher,
            )
        finally:
            db.close()

    future = _STREAM_EXECUTOR.submit(_run_turn)

    def _events():
        started = time.perf_counter()
        yield _sse("started", {"conversation_id": str(conversation_id)})
        while not future.done():
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            yield _sse(
                "progress",
                {
                    "stage": "agent_loop",
                    "elapsed_ms": round(elapsed_ms, 1),
                },
            )
            time.sleep(0.5)
        try:
            turn = future.result()
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {"message": str(exc)})
            return
        payload = _turn_to_reply(turn).model_dump(mode="json")
        payload["server_ms"] = round(turn.server_ms, 1)
        yield _sse("done", payload)

    return StreamingResponse(
        _events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _turn_to_reply(turn) -> TurnReply:
    return TurnReply(
        user=MessageOut.model_validate(turn.user),
        assistant=MessageOut.model_validate(turn.assistant),
        agent_run_id=turn.agent_run.id,
        used_search=turn.agent_run.used_search,
        status=turn.agent_run.status,  # type: ignore[arg-type]
        conversation_title=turn.conversation_title,
    )
