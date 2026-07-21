"""F05 conversation API test cases (F05-T01 … F05-T07)."""

from __future__ import annotations

import time
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_api.db.models import Conversation


pytestmark = pytest.mark.integration


def test_f05_t01_create_conversation_appears_in_default_list(client_a: TestClient) -> None:
    """F05-T01: create → 201 active; appears in default list."""
    resp = client_a.post("/v1/conversations", json={})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "active"
    assert body["title"] == "新会话"
    conv_id = body["id"]

    listed = client_a.get("/v1/conversations")
    assert listed.status_code == 200
    ids = [c["id"] for c in listed.json()]
    assert conv_id in ids


def test_f05_t02_messages_ordered_by_create_at(client_a: TestClient) -> None:
    """F05-T02: GET history returns 3 messages ordered by create_at ascending."""
    conv_id = client_a.post("/v1/conversations", json={"title": "hist"}).json()["id"]
    for content in ("m1", "m2", "m3"):
        r = client_a.post(
            f"/v1/conversations/{conv_id}/messages",
            json={"role": "user", "content": content},
        )
        assert r.status_code == 201
        time.sleep(0.02)

    hist = client_a.get(f"/v1/conversations/{conv_id}/messages")
    assert hist.status_code == 200
    messages = hist.json()
    assert len(messages) == 3
    assert [m["content"] for m in messages] == ["m1", "m2", "m3"]
    times = [datetime.fromisoformat(m["create_at"]) for m in messages]
    assert times == sorted(times)


def test_f05_t03_archive_hides_from_default_list(client_a: TestClient) -> None:
    """F05-T03: archive → gone from default; visible in archived list."""
    conv_id = client_a.post("/v1/conversations", json={}).json()["id"]
    arch = client_a.post(f"/v1/conversations/{conv_id}/archive")
    assert arch.status_code == 200
    assert arch.json()["status"] == "archived"

    default_ids = [c["id"] for c in client_a.get("/v1/conversations").json()]
    assert conv_id not in default_ids

    archived_ids = [
        c["id"] for c in client_a.get("/v1/conversations", params={"status": "archived"}).json()
    ]
    assert conv_id in archived_ids


def test_f05_t04_post_message_to_archived_returns_409(client_a: TestClient) -> None:
    """F05-T04: POST message on archived conversation → 409."""
    conv_id = client_a.post("/v1/conversations", json={}).json()["id"]
    assert client_a.post(f"/v1/conversations/{conv_id}/archive").status_code == 200
    resp = client_a.post(
        f"/v1/conversations/{conv_id}/messages",
        json={"role": "user", "content": "nope"},
    )
    assert resp.status_code == 409


def test_f05_t05_unarchive_allows_messages_again(client_a: TestClient) -> None:
    """F05-T05: unarchive → back in default list; can post messages."""
    conv_id = client_a.post("/v1/conversations", json={}).json()["id"]
    client_a.post(f"/v1/conversations/{conv_id}/archive")
    unarch = client_a.post(f"/v1/conversations/{conv_id}/unarchive")
    assert unarch.status_code == 200
    assert unarch.json()["status"] == "active"

    default_ids = [c["id"] for c in client_a.get("/v1/conversations").json()]
    assert conv_id in default_ids

    msg = client_a.post(
        f"/v1/conversations/{conv_id}/messages",
        json={"role": "user", "content": "again"},
    )
    assert msg.status_code == 201


def test_f05_t06_cross_tenant_get_returns_404(client_a: TestClient, switch_to_b) -> None:
    """F05-T06: tenant-B GET tenant-A conversation → 404."""
    conv_id = client_a.post("/v1/conversations", json={}).json()["id"]
    client_b = switch_to_b()
    resp = client_b.get(f"/v1/conversations/{conv_id}/messages")
    assert resp.status_code == 404


def test_f05_t07_soft_deleted_not_in_lists(client_a: TestClient) -> None:
    """F05-T07: soft-deleted conversation invisible in both lists."""
    conv_id = client_a.post("/v1/conversations", json={}).json()["id"]
    deleted = client_a.delete(f"/v1/conversations/{conv_id}")
    assert deleted.status_code == 204

    active_ids = [c["id"] for c in client_a.get("/v1/conversations").json()]
    archived_ids = [
        c["id"] for c in client_a.get("/v1/conversations", params={"status": "archived"}).json()
    ]
    assert conv_id not in active_ids
    assert conv_id not in archived_ids


def test_f05_timestamp_trigger_on_conversation(client_a: TestClient, db: Session) -> None:
    """create_at stable; update_at advances on update (trigger)."""
    conv_id = client_a.post("/v1/conversations", json={"title": "ts"}).json()["id"]
    row = db.scalar(select(Conversation).where(Conversation.id == conv_id))
    assert row is not None
    create_at = row.create_at
    update_at = row.update_at
    assert create_at is not None
    assert update_at is not None

    time.sleep(0.05)
    client_a.post(f"/v1/conversations/{conv_id}/archive")
    db.expire_all()
    row2 = db.scalar(select(Conversation).where(Conversation.id == conv_id))
    assert row2 is not None
    assert row2.create_at == create_at
    assert row2.update_at > update_at
