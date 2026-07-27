"""F11 tenant public API tests (F11-T01 … F11-T08)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_api.agent.constants import TOOL_SEARCH_KNOWLEDGE
from rag_api.api.dependencies import get_llm_client
from rag_api.clients.llm import LlmResult, ScriptedLlmClient, ToolCall
from rag_api.db.models import ApiKey
from rag_api.indexing.search import ChunkHit, FakeKnowledgeSearcher
from rag_api.services.api_keys import hash_api_key_secret
from rag_api.services.rate_limit import api_key_limiter
from tests.helpers import tenant_host_headers

HEADERS_A = tenant_host_headers("pytest-a")
HEADERS_B = tenant_host_headers("pytest-b")


@pytest.fixture(autouse=True)
def _reset_api_key_limiter():
    api_key_limiter.reset()
    yield
    api_key_limiter.reset()


def _bearer(secret: str, headers: dict[str, str] | None = None) -> dict[str, str]:
    base = dict(headers or HEADERS_A)
    base["Authorization"] = f"Bearer {secret}"
    return base


def _create_key(client: TestClient, *, name: str | None = "integ") -> dict:
    body: dict = {}
    if name is not None:
        body["name"] = name
    res = client.post("/v1/admin/api-keys", headers=HEADERS_A, json=body)
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.integration
def test_f11_t01_create_key_plaintext_once(client_a: TestClient, db: Session, tenants: dict):
    """F11-T01: create Key → 201 with rk_live_ secret; DB has hash only."""
    body = _create_key(client_a, name="prod")
    assert body["secret"].startswith("rk_live_")
    assert body["key_prefix"].startswith("rk_live_")
    assert len(body["key_prefix"]) == len("rk_live_") + 8
    assert body["secret"].startswith(body["key_prefix"])
    assert body["status"] == "active"

    row = db.scalar(select(ApiKey).where(ApiKey.id == body["id"]))
    assert row is not None
    assert row.key_hash == hash_api_key_secret(body["secret"])
    assert row.key_hash != body["secret"]
    # No plaintext column / value stored as secret
    assert not hasattr(row, "secret")
    dumped = str(row.__dict__)
    assert body["secret"] not in dumped


@pytest.mark.integration
def test_f11_t02_search_tenant_isolated(
    client_a: TestClient,
    tenants: dict,
    fake_searcher: FakeKnowledgeSearcher,
):
    """F11-T02: search hits only host tenant corpus."""
    unique = "F11UNIQUEPHRASE_TENANT_A_ONLY"
    fake_searcher.seed(
        tenants["tenant_a"].tenant_id,
        [
            ChunkHit(
                chunk_id="c-a",
                document_id="d-a",
                section_id="s-a",
                path="政策 > 退款",
                content=f"本租户内容含 {unique}",
                score=1.0,
            )
        ],
    )
    fake_searcher.seed(
        tenants["tenant_b"].tenant_id,
        [
            ChunkHit(
                chunk_id="c-b",
                document_id="d-b",
                section_id="s-b",
                path="其他 > 秘密",
                content="tenant-B secret should not leak",
                score=1.0,
            )
        ],
    )
    created = _create_key(client_a)
    secret = created["secret"]

    res = client_a.post(
        "/api/v1/search",
        headers=_bearer(secret),
        json={"query": unique, "top_k": 5},
    )
    assert res.status_code == 200, res.text
    hits = res.json()["hits"]
    assert len(hits) >= 1
    assert all(unique in h["content"] for h in hits)
    assert all("tenant-B" not in h["content"] for h in hits)
    assert hits[0]["path"]
    assert hits[0]["content"]


@pytest.mark.integration
def test_f11_t03_chat_grounded(
    client_a: TestClient,
    app,
    tenants: dict,
    fake_searcher: FakeKnowledgeSearcher,
):
    """F11-T03: chat asks indexed fact → 200 with conversation_id + grounded reply."""
    fake_searcher.seed(
        tenants["tenant_a"].tenant_id,
        [
            ChunkHit(
                chunk_id="c1",
                document_id="d1",
                section_id="s1",
                path="退货政策 > 时效",
                content="退货政策：顾客可在购买后 30 天内申请退货。",
                score=1.0,
            )
        ],
    )
    llm = ScriptedLlmClient(
        [
            LlmResult(
                tool_calls=[
                    ToolCall(
                        id="t1",
                        name=TOOL_SEARCH_KNOWLEDGE,
                        arguments={"query": "退货"},
                    )
                ]
            ),
            LlmResult(content="根据知识库（退货政策 > 时效），退货窗口为 30 天。"),
        ]
    )
    app.dependency_overrides[get_llm_client] = lambda: llm

    secret = _create_key(client_a)["secret"]
    res = client_a.post(
        "/api/v1/chat",
        headers=_bearer(secret),
        json={"message": "退货要多久？"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["conversation_id"]
    assert "30" in body["message"]
    assert "退货" in body["message"] or "时效" in body["message"]
    assert body["used_search"] is True


@pytest.mark.integration
def test_f11_t04_missing_or_bad_key_unauthorized(client_a: TestClient):
    """F11-T04: no/wrong Authorization → 401 unauthorized."""
    created = _create_key(client_a)
    missing = client_a.post(
        "/api/v1/search",
        headers=HEADERS_A,
        json={"query": "x"},
    )
    assert missing.status_code == 401, missing.text
    assert missing.json()["error"]["code"] == "unauthorized"

    bad = client_a.post(
        "/api/v1/search",
        headers=_bearer("rk_live_not_a_real_key_value"),
        json={"query": "x"},
    )
    assert bad.status_code == 401, bad.text
    assert bad.json()["error"]["code"] == "unauthorized"

    # wrong bearer still unrelated to a real key
    _ = created


@pytest.mark.integration
def test_f11_t05_cross_tenant_forbidden(client_a: TestClient):
    """F11-T05: tenant-A key + Host=tenant-B → 403."""
    secret = _create_key(client_a)["secret"]
    res = client_a.post(
        "/api/v1/search",
        headers=_bearer(secret, HEADERS_B),
        json={"query": "anything"},
    )
    assert res.status_code == 403, res.text
    assert res.json()["error"]["code"] == "forbidden"


@pytest.mark.integration
def test_f11_t06_revoked_key_unauthorized(client_a: TestClient):
    """F11-T06: revoked key → 401."""
    created = _create_key(client_a)
    rev = client_a.post(
        f"/v1/admin/api-keys/{created['id']}/revoke",
        headers=HEADERS_A,
    )
    assert rev.status_code == 200, rev.text
    assert rev.json()["status"] == "revoked"

    res = client_a.post(
        "/api/v1/chat",
        headers=_bearer(created["secret"]),
        json={"message": "hello"},
    )
    assert res.status_code == 401, res.text
    assert res.json()["error"]["code"] == "unauthorized"


@pytest.mark.integration
def test_f11_t07_rate_limited(client_a: TestClient):
    """F11-T07: >60 req/min → 429 rate_limited."""
    secret = _create_key(client_a)["secret"]
    headers = _bearer(secret)
    for i in range(60):
        r = client_a.post("/api/v1/search", headers=headers, json={"query": f"q{i}"})
        assert r.status_code == 200, f"req {i}: {r.text}"
    limited = client_a.post(
        "/api/v1/search",
        headers=headers,
        json={"query": "overflow"},
    )
    assert limited.status_code == 429, limited.text
    assert limited.json()["error"]["code"] == "rate_limited"


@pytest.mark.integration
def test_f11_t08_list_keys_no_secret(client_a: TestClient):
    """F11-T08: list Keys → prefix mask only, no secret/hash."""
    created = _create_key(client_a, name="listed")
    listed = client_a.get("/v1/admin/api-keys", headers=HEADERS_A)
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert len(rows) >= 1
    match = next(r for r in rows if r["id"] == created["id"])
    assert match["key_prefix"] == created["key_prefix"]
    assert "secret" not in match
    assert "key_hash" not in match
