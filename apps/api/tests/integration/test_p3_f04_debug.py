"""P3-F04 Admin Debug Page tests (P3-F04-T01 … T07)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from rag_api.agent.constants import TOOL_SEARCH_KNOWLEDGE
from rag_api.api.dependencies import get_llm_client
from rag_api.clients.llm import LlmResult, ScriptedLlmClient, ToolCall
from rag_api.config import get_settings
from rag_api.ingestion.search import ChunkHit, FakeKnowledgeSearcher
from tests.helpers import tenant_host_headers

pytestmark = pytest.mark.integration

HEADERS_A = tenant_host_headers("pytest-a")
HEADERS_B = tenant_host_headers("pytest-b")
UNIQUE_PHRASE = "P3F04_UNIQUE_INDEX_PHRASE_ZXQ"


@pytest.fixture
def enable_admin_debug(monkeypatch: pytest.MonkeyPatch):
    """Enable Admin Debug for the duration of a test."""
    monkeypatch.setenv("ENABLE_ADMIN_DEBUG", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def disable_admin_debug(monkeypatch: pytest.MonkeyPatch):
    """Disable Admin Debug for the duration of a test."""
    monkeypatch.setenv("ENABLE_ADMIN_DEBUG", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _seed_unique(searcher: FakeKnowledgeSearcher, tenant_id) -> None:
    searcher.seed(
        tenant_id,
        [
            ChunkHit(
                chunk_id="c-p3f04",
                document_id="d-p3f04",
                section_id="s-p3f04",
                path="调试 > 索引短语",
                content=f"本节包含独特短语 {UNIQUE_PHRASE} 用于检索验收。",
                score=1.0,
            )
        ],
    )


def test_p3_f04_t01_search_only_hits_without_llm(
    client_a: TestClient,
    tenants: dict,
    fake_searcher: FakeKnowledgeSearcher,
    scripted_llm: ScriptedLlmClient,
    enable_admin_debug,
) -> None:
    """P3-F04-T01: Search only hits indexed phrase; zero LLM calls."""
    _seed_unique(fake_searcher, tenants["tenant_a"].tenant_id)
    before = len(scripted_llm.calls)
    res = client_a.post(
        "/v1/admin/debug/search",
        headers=HEADERS_A,
        json={"query": UNIQUE_PHRASE, "top_k": 5},
    )
    assert res.status_code == 200, res.text
    hits = res.json()["hits"]
    assert len(hits) >= 1
    assert any(UNIQUE_PHRASE in h["content"] for h in hits)
    assert len(scripted_llm.calls) == before


def test_p3_f04_t02_unpublished_phrase_no_hit(
    client_a: TestClient,
    tenants: dict,
    fake_searcher: FakeKnowledgeSearcher,
    enable_admin_debug,
) -> None:
    """P3-F04-T02: unpublished phrase is not in searchable corpus → 0 hits.

    FakeKnowledgeSearcher mirrors published-only index (only seeded/published content).
    """
    unpublished = "P3F04_UNPUBLISHED_PHRASE_NEVER_INDEXED"
    # Do not seed unpublished phrase — same as unpublished docs not entering is_latest index.
    _seed_unique(fake_searcher, tenants["tenant_a"].tenant_id)
    res = client_a.post(
        "/v1/admin/debug/search",
        headers=HEADERS_A,
        json={"query": unpublished, "top_k": 5},
    )
    assert res.status_code == 200, res.text
    assert res.json()["hits"] == []


def test_p3_f04_t03_tenant_isolation(
    client_a: TestClient,
    switch_to_b,
    tenants: dict,
    fake_searcher: FakeKnowledgeSearcher,
    enable_admin_debug,
) -> None:
    """P3-F04-T03: tenant-A corpus is invisible to tenant-B Search only."""
    _seed_unique(fake_searcher, tenants["tenant_a"].tenant_id)
    client_b = switch_to_b()
    res = client_b.post(
        "/v1/admin/debug/search",
        headers=HEADERS_B,
        json={"query": UNIQUE_PHRASE, "top_k": 5},
    )
    assert res.status_code == 200, res.text
    assert res.json()["hits"] == []


def test_p3_f04_t04_agent_debug_payload(
    client_a: TestClient,
    app,
    tenants: dict,
    fake_searcher: FakeKnowledgeSearcher,
    enable_admin_debug,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P3-F04-T04: Agent debug returns answer + debug fields; no API key strings."""
    secret = "sk-test-p3f04-qwen-secret-value-xyz"
    monkeypatch.setenv("QWEN_API_KEY", secret)
    get_settings.cache_clear()

    _seed_unique(fake_searcher, tenants["tenant_a"].tenant_id)
    llm = ScriptedLlmClient(
        [
            LlmResult(
                tool_calls=[
                    ToolCall(
                        id="t1",
                        name=TOOL_SEARCH_KNOWLEDGE,
                        arguments={"query": UNIQUE_PHRASE},
                    )
                ]
            ),
            LlmResult(content=f"命中短语：{UNIQUE_PHRASE}"),
        ]
    )
    app.dependency_overrides[get_llm_client] = lambda: llm

    res = client_a.post(
        "/v1/admin/debug/chat",
        headers=HEADERS_A,
        json={"content": f"请查找 {UNIQUE_PHRASE}"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["assistant"]["content"]
    debug = body["debug"]
    assert "context_messages" in debug
    assert len(debug["context_messages"]) >= 1
    assert "history" in debug
    assert isinstance(debug["top_k_hits"], list)
    assert len(debug["top_k_hits"]) >= 1
    assert any(UNIQUE_PHRASE in h["content"] for h in debug["top_k_hits"])
    assert len(debug["llm_calls"]) >= 1
    dumped = json.dumps(body, ensure_ascii=False)
    assert secret not in dumped
    assert "Authorization" not in dumped or "[REDACTED]" in dumped


def test_p3_f04_t05_unauthenticated_api_401(
    client: TestClient,
    enable_admin_debug,
) -> None:
    """P3-F04-T05 (api part): unauthenticated debug API → 401."""
    res = client.post(
        "/v1/admin/debug/search",
        headers=HEADERS_A,
        json={"query": "hello", "top_k": 5},
    )
    assert res.status_code == 401


def test_p3_f04_t06_disabled_returns_404(
    client_a: TestClient,
    disable_admin_debug,
) -> None:
    """P3-F04-T06: ENABLE_ADMIN_DEBUG=false → 404 for probe and POST endpoints."""
    assert client_a.get("/v1/admin/debug", headers=HEADERS_A).status_code == 404
    assert (
        client_a.post(
            "/v1/admin/debug/search",
            headers=HEADERS_A,
            json={"query": "x", "top_k": 5},
        ).status_code
        == 404
    )
    assert (
        client_a.post(
            "/v1/admin/debug/chat",
            headers=HEADERS_A,
            json={"content": "hello"},
        ).status_code
        == 404
    )


def test_p3_f04_t07_portal_vs_debug_reply_match(
    client_a: TestClient,
    app,
    tenants: dict,
    fake_searcher: FakeKnowledgeSearcher,
    enable_admin_debug,
) -> None:
    """P3-F04-T07: same mock LLM + input → Portal and debug assistant.content identical."""
    _seed_unique(fake_searcher, tenants["tenant_a"].tenant_id)
    reply_text = "P3F04_FIXED_REPLY_TEXT_FOR_PARITY"

    def _scripted() -> ScriptedLlmClient:
        return ScriptedLlmClient(
            [
                LlmResult(
                    tool_calls=[
                        ToolCall(
                            id="t1",
                            name=TOOL_SEARCH_KNOWLEDGE,
                            arguments={"query": UNIQUE_PHRASE},
                        )
                    ]
                ),
                LlmResult(content=reply_text),
            ]
        )

    app.dependency_overrides[get_llm_client] = _scripted
    portal = client_a.post(
        "/v1/conversations/messages",
        headers=HEADERS_A,
        json={"role": "user", "content": f"问 {UNIQUE_PHRASE}", "conversation_id": None},
    )
    assert portal.status_code == 201, portal.text

    app.dependency_overrides[get_llm_client] = _scripted
    debug = client_a.post(
        "/v1/admin/debug/chat",
        headers=HEADERS_A,
        json={"content": f"问 {UNIQUE_PHRASE}"},
    )
    assert debug.status_code == 201, debug.text
    assert portal.json()["assistant"]["content"] == debug.json()["assistant"]["content"]
    assert portal.json()["assistant"]["content"] == reply_text
