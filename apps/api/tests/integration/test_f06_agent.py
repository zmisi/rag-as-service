"""F06 RAG Agent Loop tests (F06-T01 … F06-T11)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rag_api.agent.constants import MAX_STEPS, NO_HIT_PHRASE, TOOL_SEARCH_KNOWLEDGE
from rag_api.api.dependencies import get_llm_client
from rag_api.clients.llm import LlmResult, LlmTimeoutError, ScriptedLlmClient, ToolCall
from rag_api.db.models import AgentRun, Message
from rag_api.indexing.search import ChunkHit, FakeKnowledgeSearcher

pytestmark = pytest.mark.integration

BANNED_FABRICATION = ("伪造书名", "《不存在的法规》", "条款号XYZ-999")


def _seed_return_policy(searcher: FakeKnowledgeSearcher, tenant_id) -> None:
    searcher.seed(
        tenant_id,
        [
            ChunkHit(
                chunk_id="c1",
                document_id="d1",
                content="退货政策：顾客可在购买后 30 天内申请退货。退货窗口 30 天。",
                score=1.0,
            )
        ],
    )


def test_f06_t01_rag_search_grounded(
    client_a: TestClient,
    app,
    tenants: dict,
    fake_searcher: FakeKnowledgeSearcher,
) -> None:
    """F06-T01: indexed corpus → search_knowledge; used_search; answer grounded."""
    _seed_return_policy(fake_searcher, tenants["tenant_a"].id)
    llm = ScriptedLlmClient(
        [
            LlmResult(
                tool_calls=[
                    ToolCall(
                        id="t1",
                        name=TOOL_SEARCH_KNOWLEDGE,
                        arguments={"query": "退货政策"},
                    )
                ]
            ),
            LlmResult(content="根据知识库，退货窗口为 30 天。"),
        ]
    )
    app.dependency_overrides[get_llm_client] = lambda: llm

    conv_id = client_a.post("/v1/conversations", json={}).json()["id"]
    resp = client_a.post(
        f"/v1/conversations/{conv_id}/messages",
        json={"role": "user", "content": "退货政策是什么？"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["used_search"] is True
    assert body["status"] == "completed"
    assert body["conversation_title"] == "退货政策是什么？"
    assert "30" in body["assistant"]["content"]
    listed = client_a.get("/v1/conversations").json()
    assert any(c["id"] == conv_id and c["title"] == "退货政策是什么？" for c in listed)


def test_f06_t02_no_hit_no_fabrication(
    client_a: TestClient,
    app,
    fake_searcher: FakeKnowledgeSearcher,
) -> None:
    """F06-T02: empty search → no-hit phrasing; no banned fabrications."""
    # empty corpus by default
    llm = ScriptedLlmClient(
        [
            LlmResult(
                tool_calls=[
                    ToolCall(id="t1", name=TOOL_SEARCH_KNOWLEDGE, arguments={"query": "火星签证"})
                ]
            ),
            LlmResult(content=f"{NO_HIT_PHRASE}，无法回答该问题。"),
        ]
    )
    app.dependency_overrides[get_llm_client] = lambda: llm

    conv_id = client_a.post("/v1/conversations", json={"title": "t02"}).json()["id"]
    resp = client_a.post(
        f"/v1/conversations/{conv_id}/messages",
        json={"role": "user", "content": "火星签证怎么办理？"},
    )
    assert resp.status_code == 201
    text = resp.json()["assistant"]["content"]
    assert NO_HIT_PHRASE in text
    for banned in BANNED_FABRICATION:
        assert banned not in text


def test_f06_t03_chitchat_no_required_search(client_a: TestClient, app) -> None:
    """F06-T03: hello → loop; search optional; polite reply."""
    llm = ScriptedLlmClient([LlmResult(content="你好！有什么可以帮您的吗？")])
    app.dependency_overrides[get_llm_client] = lambda: llm

    conv_id = client_a.post("/v1/conversations", json={"title": "t03"}).json()["id"]
    resp = client_a.post(
        f"/v1/conversations/{conv_id}/messages",
        json={"role": "user", "content": "你好"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["used_search"] is False
    assert "你好" in body["assistant"]["content"] or "帮" in body["assistant"]["content"]


def test_f06_t04_vague_clarify(client_a: TestClient, app) -> None:
    """F06-T04: vague question → clarify; no invented KB facts."""
    llm = ScriptedLlmClient(
        [LlmResult(content="请问您指的是哪一份文档或哪项政策？信息不足，无法检索。")]
    )
    app.dependency_overrides[get_llm_client] = lambda: llm

    conv_id = client_a.post("/v1/conversations", json={"title": "t04"}).json()["id"]
    resp = client_a.post(
        f"/v1/conversations/{conv_id}/messages",
        json={"role": "user", "content": "那个呢？"},
    )
    assert resp.status_code == 201
    text = resp.json()["assistant"]["content"]
    assert "请问" in text or "不足" in text
    for banned in BANNED_FABRICATION:
        assert banned not in text


def test_f06_t05_history_compression(
    client_a: TestClient,
    app,
    db: Session,
    tenants: dict,
) -> None:
    """F06-T05: 25+ messages → compress path keeps recent; still answers."""
    from rag_api.db.models import Conversation

    conv = Conversation(
        tenant_id=tenants["tenant_a"].id,
        user_id=tenants["user_a"].id,
        title="t05",
        status="active",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    for i in range(25):
        role = "user" if i % 2 == 0 else "assistant"
        db.add(
            Message(
                conversation_id=conv.id,
                tenant_id=tenants["tenant_a"].id,
                role=role,
                content=f"msg-{i}",
            )
        )
    db.commit()

    llm = ScriptedLlmClient([LlmResult(content="根据近期对话，可以继续。")])
    app.dependency_overrides[get_llm_client] = lambda: llm

    resp = client_a.post(
        f"/v1/conversations/{conv.id}/messages",
        json={"role": "user", "content": "继续"},
    )
    assert resp.status_code == 201
    assert resp.json()["assistant"]["content"]
    # Scripted LLM should have received a system summary when history was long
    assert any(
        m.get("role") == "system" and "历史摘要" in (m.get("content") or "")
        for call in llm.calls
        for m in call["messages"]
    )


def test_f06_t06_max_steps_truncated(
    client_a: TestClient,
    app,
    db: Session,
    tenants: dict,
    fake_searcher: FakeKnowledgeSearcher,
) -> None:
    """F06-T06: endless tools → truncated within MAX_STEPS."""
    _seed_return_policy(fake_searcher, tenants["tenant_a"].id)
    tool_step = LlmResult(
        tool_calls=[
            ToolCall(id="tx", name=TOOL_SEARCH_KNOWLEDGE, arguments={"query": "退货"})
        ]
    )
    # MAX_STEPS tool-only results, then forced summary may call LLM once more without tools
    script: list = [tool_step] * MAX_STEPS + [LlmResult(content="步数用尽后的总结。")]
    llm = ScriptedLlmClient(script)
    app.dependency_overrides[get_llm_client] = lambda: llm

    conv_id = client_a.post("/v1/conversations", json={"title": "t06"}).json()["id"]
    resp = client_a.post(
        f"/v1/conversations/{conv_id}/messages",
        json={"role": "user", "content": "反复检索"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "truncated"
    run = db.scalar(select(AgentRun).where(AgentRun.id == body["agent_run_id"]))
    assert run is not None
    assert run.step_count <= MAX_STEPS
    assert run.status == "truncated"


def test_f06_t07_tenant_isolation(
    client_a: TestClient,
    app,
    switch_to_b,
    tenants: dict,
    fake_searcher: FakeKnowledgeSearcher,
) -> None:
    """F06-T07: tenant-A corpus not visible to tenant-B search."""
    _seed_return_policy(fake_searcher, tenants["tenant_a"].id)
    # B has empty corpus

    llm = ScriptedLlmClient(
        [
            LlmResult(
                tool_calls=[
                    ToolCall(
                        id="t1",
                        name=TOOL_SEARCH_KNOWLEDGE,
                        arguments={"query": "退货窗口 30 天"},
                    )
                ]
            ),
            LlmResult(content=NO_HIT_PHRASE),
        ]
    )
    app.dependency_overrides[get_llm_client] = lambda: llm

    client_b = switch_to_b()
    conv_id = client_b.post("/v1/conversations", json={"title": "t07"}).json()["id"]
    resp = client_b.post(
        f"/v1/conversations/{conv_id}/messages",
        json={"role": "user", "content": "退货窗口是多少天？"},
    )
    assert resp.status_code == 201
    text = resp.json()["assistant"]["content"]
    assert NO_HIT_PHRASE in text
    assert "30 天" not in text
    hits = fake_searcher.search(tenants["tenant_b"].id, "退货窗口 30 天", top_k=5)
    assert hits == []


def test_f06_t08_archived_no_agent_run(
    client_a: TestClient,
    db: Session,
) -> None:
    """F06-T08: archived → 409; no successful agent_run."""
    conv_id = client_a.post("/v1/conversations", json={"title": "t08"}).json()["id"]
    assert client_a.post(f"/v1/conversations/{conv_id}/archive").status_code == 200
    before = db.scalar(select(func.count()).select_from(AgentRun)) or 0
    resp = client_a.post(
        f"/v1/conversations/{conv_id}/messages",
        json={"role": "user", "content": "hi"},
    )
    assert resp.status_code == 409
    after = db.scalar(select(func.count()).select_from(AgentRun)) or 0
    assert after == before
    completed = db.scalars(
        select(AgentRun).where(AgentRun.status == "completed")
    ).all()
    # No new completed runs for this conversation
    assert all(str(r.conversation_id) != conv_id for r in completed)


def test_f06_t09_llm_timeout(
    client_a: TestClient,
    app,
    db: Session,
) -> None:
    """F06-T09: LLM timeout → error reply; loop ends."""
    llm = ScriptedLlmClient([LlmTimeoutError("timeout")])
    app.dependency_overrides[get_llm_client] = lambda: llm

    conv_id = client_a.post("/v1/conversations", json={"title": "t09"}).json()["id"]
    resp = client_a.post(
        f"/v1/conversations/{conv_id}/messages",
        json={"role": "user", "content": "会超时"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "error"
    assert body["assistant"]["content"]
    run = db.get(AgentRun, body["agent_run_id"])
    assert run is not None
    assert run.status == "error"
