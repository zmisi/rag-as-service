"""F12 public widget session + chat (site key + Origin; no cookie)."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from rag_api.agent.service import run_user_turn
from rag_api.api.dependencies import get_db, get_knowledge_searcher, get_llm_client
from rag_api.api.dependencies.widget import WidgetAuthContext, require_widget_site_key
from rag_api.api.schemas.conversations import MessageOut, TurnReply
from rag_api.api.schemas.widget import WidgetChatCreate, WidgetSessionOut
from rag_api.clients.llm import LlmClient
from rag_api.db.session import get_session_factory
from rag_api.ingestion.search import KnowledgeSearcher
from rag_api.services import conversations as conv_svc

router = APIRouter(prefix="/widget", tags=["widget"])
_STREAM_EXECUTOR = ThreadPoolExecutor(max_workers=8)


def _turn_to_reply(turn, *, conversation_id: UUID) -> TurnReply:
    return TurnReply(
        user=MessageOut.model_validate(turn.user),
        assistant=MessageOut.model_validate(turn.assistant),
        agent_run_id=turn.agent_run.id,
        used_search=turn.agent_run.used_search,
        status=turn.loop.status,  # type: ignore[arg-type]
        conversation_title=turn.conversation_title,
        conversation_id=conversation_id,
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post(
    "/session",
    response_model=WidgetSessionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_widget_session(
    response: Response,
    db: Session = Depends(get_db),
    auth: WidgetAuthContext = Depends(require_widget_site_key),
) -> WidgetSessionOut:
    conv = conv_svc.create_conversation(
        db,
        tenant_id=auth.tenant_id,
        site_key_id=auth.site_key_id,
        title=None,
    )
    return WidgetSessionOut(conversation_id=conv.id)


@router.post("/chat", response_model=TurnReply, status_code=status.HTTP_201_CREATED)
def widget_chat(
    body: WidgetChatCreate,
    response: Response,
    db: Session = Depends(get_db),
    auth: WidgetAuthContext = Depends(require_widget_site_key),
    llm: LlmClient = Depends(get_llm_client),
    searcher: KnowledgeSearcher = Depends(get_knowledge_searcher),
) -> TurnReply:
    conversation_id = conv_svc.resolve_conversation_for_widget_message(
        db,
        tenant_id=auth.tenant_id,
        site_key_id=auth.site_key_id,
        conversation_id=body.conversation_id,
        content=body.content,
    )
    turn = run_user_turn(
        db,
        conversation_id=conversation_id,
        tenant_id=auth.tenant_id,
        site_key_id=auth.site_key_id,
        content=body.content,
        llm=llm,
        searcher=searcher,
    )
    response.headers["Server-Timing"] = f"turn;dur={turn.server_ms:.1f}"
    return _turn_to_reply(turn, conversation_id=conversation_id)


@router.post("/chat/stream")
def widget_chat_stream(
    body: WidgetChatCreate,
    auth: WidgetAuthContext = Depends(require_widget_site_key),
    llm: LlmClient = Depends(get_llm_client),
    searcher: KnowledgeSearcher = Depends(get_knowledge_searcher),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    conversation_id = conv_svc.resolve_conversation_for_widget_message(
        db,
        tenant_id=auth.tenant_id,
        site_key_id=auth.site_key_id,
        conversation_id=body.conversation_id,
        content=body.content,
    )
    session_factory = get_session_factory()
    tenant_id = auth.tenant_id
    site_key_id = auth.site_key_id
    content = body.content

    def _run_turn():
        turn_db = session_factory()
        try:
            return run_user_turn(
                turn_db,
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                site_key_id=site_key_id,
                content=content,
                llm=llm,
                searcher=searcher,
            )
        finally:
            turn_db.close()

    future = _STREAM_EXECUTOR.submit(_run_turn)

    def _events():
        started = time.perf_counter()
        yield _sse("started", {"conversation_id": str(conversation_id)})
        while not future.done():
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            yield _sse(
                "progress",
                {"stage": "agent_loop", "elapsed_ms": round(elapsed_ms, 1)},
            )
            time.sleep(0.5)
        try:
            turn = future.result()
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {"message": str(exc)})
            return
        payload = _turn_to_reply(turn, conversation_id=conversation_id).model_dump(
            mode="json"
        )
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
