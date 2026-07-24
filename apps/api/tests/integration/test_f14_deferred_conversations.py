"""F14 deferred conversation API tests (F14-T02, T05–T07)."""

from __future__ import annotations

import io

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rag_api.db.models import Conversation, FaqSuggestionStats
from tests.helpers import (
    issue_session_for_user,
    set_client_session_cookie,
    tenant_host_headers,
)

HEADERS_A = tenant_host_headers("pytest-a")
HEADERS_B = tenant_host_headers("pytest-b")
TXT_BODY = b"FAQ body\n"


def _count_conversations(db: Session, *, tenant_id, user_id) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(Conversation)
            .where(
                Conversation.tenant_id == tenant_id,
                Conversation.user_id == user_id,
                Conversation.deleted_at.is_(None),
            )
        )
        or 0
    )


def _create_upload_publish(client, headers, *, title: str) -> dict:
    created = client.post("/v1/documents", headers=headers)
    assert created.status_code == 201, created.text
    doc_id = created.json()["id"]
    up = client.post(
        f"/v1/documents/{doc_id}/files",
        headers=headers,
        files={"file": ("note.txt", io.BytesIO(TXT_BODY), "text/plain")},
    )
    assert up.status_code == 201, up.text
    client.patch(
        f"/v1/documents/{doc_id}",
        json={"title": title, "tag": "faq"},
        headers=headers,
    )
    client.post(f"/v1/documents/{doc_id}/submit-review", headers=headers)
    pub = client.post(f"/v1/documents/{doc_id}/publish", headers=headers)
    assert pub.status_code == 200, pub.text
    return pub.json()


@pytest.mark.integration
def test_f14_t02_first_message_creates_conversation(
    client_a, tenants: dict, db: Session
):
    """F14-T02: draft first query creates exactly one conversation + user message."""
    before = _count_conversations(
        db, tenant_id=tenants["tenant_a"].tenant_id, user_id=tenants["user_a"].user_id
    )
    resp = client_a.post(
        "/v1/conversations/messages",
        headers=HEADERS_A,
        json={"role": "user", "content": "首条延迟会话问题", "conversation_id": None},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["conversation_id"]
    assert body["user"]["content"] == "首条延迟会话问题"
    assert body["user"]["conversation_id"] == body["conversation_id"]

    after = _count_conversations(
        db, tenant_id=tenants["tenant_a"].tenant_id, user_id=tenants["user_a"].user_id
    )
    assert after == before + 1

    msgs = client_a.get(
        f"/v1/conversations/{body['conversation_id']}/messages", headers=HEADERS_A
    ).json()
    user_msgs = [m for m in msgs if m["role"] == "user"]
    assert len(user_msgs) == 1
    assert user_msgs[0]["content"] == "首条延迟会话问题"

    listed = client_a.get("/v1/conversations", headers=HEADERS_A).json()
    assert any(c["id"] == body["conversation_id"] for c in listed)


@pytest.mark.integration
def test_f14_t05_faq_click_then_deferred_send(
    client_a, tenants: dict, db: Session
):
    """F14-T05: FAQ click increments heat; draft send creates conversation."""
    doc = _create_upload_publish(client_a, HEADERS_A, title="FAQ for F14")
    group_id = doc["document_group_id"]
    clicked = client_a.post(
        f"/v1/portal/faq-suggestions/{group_id}/click", headers=HEADERS_A
    )
    assert clicked.status_code == 200, clicked.text
    assert clicked.json()["click_count"] == 1
    question = clicked.json()["question"]

    before = _count_conversations(
        db, tenant_id=tenants["tenant_a"].tenant_id, user_id=tenants["user_a"].user_id
    )
    resp = client_a.post(
        "/v1/conversations/messages",
        headers=HEADERS_A,
        json={"role": "user", "content": question},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["conversation_id"]
    assert (
        _count_conversations(
            db,
            tenant_id=tenants["tenant_a"].tenant_id,
            user_id=tenants["user_a"].user_id,
        )
        == before + 1
    )
    stats = db.scalar(
        select(FaqSuggestionStats).where(
            FaqSuggestionStats.tenant_id == tenants["tenant_a"].tenant_id,
            FaqSuggestionStats.document_group_id == group_id,
        )
    )
    assert stats is not None
    assert stats.click_count == 1


@pytest.mark.integration
def test_f14_t06_abandon_draft_no_row(client_a, tenants: dict, db: Session):
    """F14-T06: without calling create/message APIs, no new conversation."""
    before = _count_conversations(
        db, tenant_id=tenants["tenant_a"].tenant_id, user_id=tenants["user_a"].user_id
    )
    # Simulate draft open then leave: only list, never POST create/messages.
    listed = client_a.get("/v1/conversations", headers=HEADERS_A)
    assert listed.status_code == 200
    after = _count_conversations(
        db, tenant_id=tenants["tenant_a"].tenant_id, user_id=tenants["user_a"].user_id
    )
    assert after == before


@pytest.mark.integration
def test_f14_t07_tenant_isolation_deferred(
    client_a, switch_to_b, tenants: dict, db: Session
):
    """F14-T07: tenant-B cannot see tenant-A deferred conversation."""
    resp = client_a.post(
        "/v1/conversations/messages",
        headers=HEADERS_A,
        json={"role": "user", "content": "tenant-A only"},
    )
    assert resp.status_code == 201, resp.text
    conv_id = resp.json()["conversation_id"]

    client_b = switch_to_b()
    listed_b = client_b.get("/v1/conversations", headers=HEADERS_B).json()
    assert all(c["id"] != conv_id for c in listed_b)
    get_b = client_b.get(f"/v1/conversations/{conv_id}/messages", headers=HEADERS_B)
    assert get_b.status_code == 404

    token = issue_session_for_user(db, tenants["user_a"].user_id)
    set_client_session_cookie(client_a, token, host=HEADERS_A["Host"])
    listed_a = client_a.get("/v1/conversations", headers=HEADERS_A).json()
    assert any(c["id"] == conv_id for c in listed_a)
