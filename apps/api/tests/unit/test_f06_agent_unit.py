"""Unit tests for F06 agent helpers (no DB)."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest

from rag_api.agent.constants import HISTORY_COMPRESS_AFTER_MESSAGES, KEEP_RECENT_MESSAGES
from rag_api.agent.context import compress_history, format_chunks_as_untrusted
from rag_api.agent.loop import AgentLoop
from rag_api.agent.tools import ToolExecutor
from rag_api.clients.llm import LlmResult, ScriptedLlmClient, ToolCall
from rag_api.indexing.search import ChunkHit, FakeKnowledgeSearcher


class _Msg:
    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content


def test_compress_history_keeps_recent() -> None:
    msgs = [_Msg("user" if i % 2 == 0 else "assistant", f"m{i}") for i in range(25)]
    assert len(msgs) > HISTORY_COMPRESS_AFTER_MESSAGES
    out, meta = compress_history(msgs)  # type: ignore[arg-type]
    assert meta["compressed"] is True
    assert out[0]["role"] == "system"
    assert "历史摘要" in out[0]["content"]
    assert len(out) == 1 + KEEP_RECENT_MESSAGES


def test_format_chunks_empty() -> None:
    text = format_chunks_as_untrusted([])
    assert "无命中" in text or "无相关" in text


def test_search_ignores_model_tenant_arg() -> None:
    """tenant_id in tool arguments must not change search scope."""
    a = uuid4()
    b = uuid4()
    searcher = FakeKnowledgeSearcher()
    searcher.seed(a, [ChunkHit("1", "d", "apple-only-doc", 1.0)])
    searcher.seed(b, [ChunkHit("2", "d", "banana-only-doc", 1.0)])
    executor = ToolExecutor(searcher, a)
    result = executor.execute(
        "search_knowledge",
        {"query": "doc", "tenant_id": str(b)},
    )
    assert result.used_search is True
    contents = [c["content"] for c in result.payload["chunks"]]
    assert "apple-only-doc" in contents
    assert "banana-only-doc" not in contents


def test_f06_t10_unknown_tool_not_executed() -> None:
    """F06-T10: whitelist violation is not executed as search."""
    tenant = uuid4()
    searcher = FakeKnowledgeSearcher()
    searcher.seed(tenant, [ChunkHit("c", "d", "secret-should-not-leak", 1.0)])
    executor = ToolExecutor(searcher, tenant)
    result = executor.execute("run_shell", {"cmd": "rm -rf /"})
    assert result.ok is False
    assert result.used_search is False
    assert "run_shell" in (result.error or "")


def test_f06_t10_loop_rejects_unknown_tool() -> None:
    """F06-T10: loop terminates on unknown tool without search."""
    tenant = uuid4()
    searcher = FakeKnowledgeSearcher()
    llm = ScriptedLlmClient(
        [LlmResult(tool_calls=[ToolCall(id="x", name="delete_database", arguments={})])]
    )
    loop = AgentLoop(llm=llm, searcher=searcher, tenant_id=tenant)
    result = loop.run(history=[], user_content="hack")
    assert result.status == "error"
    assert result.used_search is False
    assert any(s.tool_name == "delete_database" for s in result.steps)


def test_f06_t11_no_intent_router_module() -> None:
    """F06-T11: no intent classification module or router branches."""
    agent_root = Path(__file__).resolve().parents[2] / "src" / "rag_api" / "agent"
    assert not (agent_root / "intent.py").exists()
    assert not (agent_root / "intent").exists()

    banned = {"rag_search", "chitchat", "clarify"}
    for path in agent_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value in banned:
                pytest.fail(f"intent label literal {node.value!r} in {path}")


def test_dev_stub_llm_greeting() -> None:
    from rag_api.clients.llm import DevStubLlmClient

    client = DevStubLlmClient()
    result = client.complete([{"role": "user", "content": "hello it is a test"}])
    assert not result.tool_calls
    assert "你好" in (result.content or "")


def test_dev_stub_llm_searches_on_question() -> None:
    from rag_api.agent.tools import tool_definitions
    from rag_api.clients.llm import DevStubLlmClient

    client = DevStubLlmClient()
    result = client.complete(
        [{"role": "user", "content": "退货政策是什么？"}],
        tools=tool_definitions(),
    )
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "search_knowledge"


def test_premature_no_hit_forces_search() -> None:
    """Model claiming no-hit without search must trigger harness search."""
    from rag_api.agent.constants import NO_HIT_PHRASE

    tenant = uuid4()
    searcher = FakeKnowledgeSearcher()
    searcher.seed(
        tenant,
        [ChunkHit("c1", "d1", "B-tree index stores keys in a balanced tree.", 1.0)],
    )
    llm = ScriptedLlmClient(
        [
            LlmResult(content=NO_HIT_PHRASE),
            LlmResult(content="根据知识库，B-tree index 是一种平衡树索引结构。"),
        ]
    )
    loop = AgentLoop(llm=llm, searcher=searcher, tenant_id=tenant)
    result = loop.run(history=[], user_content="介绍B-tree index")
    assert result.status == "completed"
    assert result.used_search is True
    assert result.step_count >= 2
    assert "B-tree" in result.reply
    assert any(
        s.step_type == "tool_call" and s.tool_name == "search_knowledge" for s in result.steps
    )


def test_qwen_maps_remote_disconnected_to_llm_timeout(monkeypatch) -> None:
    """Network drops must become LlmTimeoutError, not an unhandled 500."""
    import httpx

    from rag_api.clients.llm import LlmTimeoutError, QwenClient
    from rag_api.config import Settings

    def _boom(*_args, **_kwargs):  # noqa: ANN001
        raise httpx.RemoteProtocolError("Remote end closed connection without response")

    monkeypatch.setattr("rag_api.clients.llm._QWEN_HTTP_CLIENT.post", _boom)
    monkeypatch.setattr("rag_api.clients.llm.time.sleep", lambda _s: None)
    settings = Settings.model_construct(
        qwen_api_key="sk-test",
        qwen_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        qwen_model="qwen-plus",
    )
    client = QwenClient(settings)
    with pytest.raises(LlmTimeoutError, match="Remote end closed"):
        client.complete([{"role": "user", "content": "hi"}])


def test_qwen_retries_transient_request_error(monkeypatch) -> None:
    """SSL/connection EOF is retried; a later success is returned."""
    import httpx

    from rag_api.clients.llm import QwenClient
    from rag_api.config import Settings

    calls = {"n": 0}

    class _Resp:
        status_code = 200
        text = (
            '{"choices":[{"message":{"content":"ok","tool_calls":[]},'
            '"finish_reason":"stop"}],"usage":{},"model":"qwen-plus"}'
        )

        def raise_for_status(self) -> None:
            return None

    def _flaky(*_args, **_kwargs):  # noqa: ANN001
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError(
                "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol"
            )
        return _Resp()

    monkeypatch.setattr("rag_api.clients.llm._QWEN_HTTP_CLIENT.post", _flaky)
    monkeypatch.setattr("rag_api.clients.llm.time.sleep", lambda _s: None)
    settings = Settings.model_construct(
        qwen_api_key="sk-test",
        qwen_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        qwen_model="qwen-plus",
    )
    result = QwenClient(settings).complete([{"role": "user", "content": "hi"}])
    assert calls["n"] == 2
    assert result.content == "ok"
