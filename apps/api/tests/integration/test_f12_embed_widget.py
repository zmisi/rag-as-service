"""F12 Embed Widget API tests (F12-T01 … F12-T06)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from rag_api.services.rate_limit import widget_site_key_limiter
from tests.helpers import tenant_host_headers

HEADERS_A = tenant_host_headers("pytest-a")
ORIGIN_OK = "https://app.example.com"
ORIGIN_BAD = "https://evil.example.com"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    widget_site_key_limiter.reset()
    yield
    widget_site_key_limiter.reset()


def _widget_headers(public_key: str, origin: str = ORIGIN_OK) -> dict[str, str]:
    return {
        **HEADERS_A,
        "X-Site-Key": public_key,
        "Origin": origin,
    }


@pytest.mark.integration
def test_f12_t01_create_site_key_with_origin(client_a):
    """F12-T01: admin create site key + Origin → pk_ and whitelist."""
    res = client_a.post(
        "/v1/admin/widget-site-keys",
        headers=HEADERS_A,
        json={"allowed_origins": [ORIGIN_OK], "name": "app"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["public_key"].startswith("pk_")
    assert ORIGIN_OK in body["allowed_origins"]
    assert body["status"] == "active"


@pytest.mark.integration
def test_f12_t02_widget_chat_ok(client_a, scripted_llm):
    """F12-T02: valid Origin + site key → session/chat 200 with reply."""
    created = client_a.post(
        "/v1/admin/widget-site-keys",
        headers=HEADERS_A,
        json={"allowed_origins": [ORIGIN_OK]},
    )
    assert created.status_code == 201, created.text
    pk = created.json()["public_key"]

    session = client_a.post(
        "/v1/widget/session",
        headers=_widget_headers(pk),
    )
    assert session.status_code == 201, session.text
    conversation_id = session.json()["conversation_id"]

    chat = client_a.post(
        "/v1/widget/chat",
        headers=_widget_headers(pk),
        json={"conversation_id": conversation_id, "content": "你好"},
    )
    assert chat.status_code == 201, chat.text
    data = chat.json()
    assert data["assistant"]["content"]
    assert data["conversation_id"] == conversation_id
    assert data["status"] in ("completed", "truncated", "error")


@pytest.mark.integration
def test_f12_t03_bad_origin_forbidden(client_a):
    """F12-T03: Origin not in whitelist → 403."""
    created = client_a.post(
        "/v1/admin/widget-site-keys",
        headers=HEADERS_A,
        json={"allowed_origins": [ORIGIN_OK]},
    )
    pk = created.json()["public_key"]
    chat = client_a.post(
        "/v1/widget/chat",
        headers=_widget_headers(pk, origin=ORIGIN_BAD),
        json={"content": "hello"},
    )
    assert chat.status_code == 403, chat.text


@pytest.mark.integration
def test_f12_t04_bad_site_key_unauthorized(client_a):
    """F12-T04: wrong site key → 401."""
    created = client_a.post(
        "/v1/admin/widget-site-keys",
        headers=HEADERS_A,
        json={"allowed_origins": [ORIGIN_OK]},
    )
    assert created.status_code == 201
    chat = client_a.post(
        "/v1/widget/chat",
        headers=_widget_headers("pk_not_a_real_key"),
        json={"content": "hello"},
    )
    assert chat.status_code == 401, chat.text


@pytest.mark.integration
def test_f12_t05_revoked_site_key_unauthorized(client_a):
    """F12-T05: revoked site key → 401."""
    created = client_a.post(
        "/v1/admin/widget-site-keys",
        headers=HEADERS_A,
        json={"allowed_origins": [ORIGIN_OK]},
    )
    body = created.json()
    rev = client_a.post(
        f"/v1/admin/widget-site-keys/{body['id']}/revoke",
        headers=HEADERS_A,
    )
    assert rev.status_code == 200, rev.text
    assert rev.json()["status"] == "revoked"

    chat = client_a.post(
        "/v1/widget/chat",
        headers=_widget_headers(body["public_key"]),
        json={"content": "hello"},
    )
    assert chat.status_code == 401, chat.text


@pytest.mark.integration
def test_f12_t06_snippet_contains_widget_js_and_site_key(client_a):
    """F12-T06: snippet includes widget.js and data-site-key."""
    created = client_a.post(
        "/v1/admin/widget-site-keys",
        headers=HEADERS_A,
        json={"allowed_origins": [ORIGIN_OK]},
    )
    body = created.json()
    sn = client_a.get(
        f"/v1/admin/widget-site-keys/{body['id']}/snippet",
        headers=HEADERS_A,
    )
    assert sn.status_code == 200, sn.text
    payload = sn.json()
    assert "widget.js" in payload["snippet"]
    assert "data-site-key=" in payload["snippet"]
    assert body["public_key"] in payload["snippet"]
    assert "rk_live_" not in payload["snippet"]


@pytest.mark.integration
def test_f12_t07_widget_js_has_no_rk_live():
    """F12-T07 (static): widget.js must not contain rk_live_."""
    widget_js = (
        Path(__file__).resolve().parents[3]
        / "web"
        / "public"
        / "widget.js"
    )
    text = widget_js.read_text(encoding="utf-8")
    assert "rk_live_" not in text
    assert "data-site-key" in text or "siteKey" in text


@pytest.mark.integration
def test_f12_empty_whitelist_rejects_all(client_a):
    """Blank whitelist → all Origins rejected (403)."""
    created = client_a.post(
        "/v1/admin/widget-site-keys",
        headers=HEADERS_A,
        json={"allowed_origins": []},
    )
    pk = created.json()["public_key"]
    chat = client_a.post(
        "/v1/widget/chat",
        headers=_widget_headers(pk),
        json={"content": "hello"},
    )
    assert chat.status_code == 403, chat.text


@pytest.mark.integration
def test_f12_chat_without_prior_session(client_a):
    """Chat can create conversation on first message (no session)."""
    created = client_a.post(
        "/v1/admin/widget-site-keys",
        headers=HEADERS_A,
        json={"allowed_origins": [ORIGIN_OK]},
    )
    pk = created.json()["public_key"]
    chat = client_a.post(
        "/v1/widget/chat",
        headers=_widget_headers(pk),
        json={"content": "第一句"},
    )
    assert chat.status_code == 201, chat.text
    assert chat.json()["conversation_id"]
