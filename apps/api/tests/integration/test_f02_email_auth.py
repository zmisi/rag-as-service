"""F02 email auth test cases (F02-T01 … F02-T08)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.helpers import (
    JSON_HEADERS,
    attach_session_cookie,
    register_user,
    tenant_host_headers,
)


pytestmark = pytest.mark.integration


def test_f02_t01_successful_login(api_client: TestClient, db_session: Session) -> None:
    registered = register_user(api_client, db_session)
    api_client.cookies.clear()

    response = api_client.post(
        "/api/v1/auth/login",
        json={
            "email": registered["email"],
            "password": registered["password"],
        },
        headers=JSON_HEADERS,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["subdomain"] == registered["subdomain"]
    assert body["redirect_url"] == f"https://{registered['subdomain']}.lxzxai.com/"
    assert "/admin" not in body["redirect_url"]

    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "domain=.lxzxai.com" in set_cookie
    attach_session_cookie(api_client, response)
    assert api_client.cookies.get("pb_session")


def test_f02_t02_wrong_password(api_client: TestClient, db_session: Session) -> None:
    registered = register_user(api_client, db_session)
    api_client.cookies.clear()

    response = api_client.post(
        "/api/v1/auth/login",
        json={"email": registered["email"], "password": "wrong-password"},
        headers=JSON_HEADERS,
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_credentials"
    assert not api_client.cookies.get("pb_session")


def test_f02_t05_cross_tenant_forbidden(
    api_client: TestClient,
    db_session: Session,
) -> None:
    first = register_user(api_client, db_session, subdomain=f"tenant-a-{uuid.uuid4().hex[:6]}")
    api_client.cookies.clear()
    second = register_user(api_client, db_session, subdomain=f"tenant-b-{uuid.uuid4().hex[:6]}")

    login = api_client.post(
        "/api/v1/auth/login",
        json={"email": first["email"], "password": first["password"]},
        headers=JSON_HEADERS,
    )
    assert login.status_code == 200
    attach_session_cookie(api_client, login)

    cross = api_client.get(
        "/v1/conversations",
        headers=tenant_host_headers(second["subdomain"]),
    )
    assert cross.status_code == 403


def test_f02_t07_cookie_works_on_tenant_api(
    api_client: TestClient,
    db_session: Session,
) -> None:
    registered = register_user(api_client, db_session)
    api_client.cookies.clear()

    login = api_client.post(
        "/api/v1/auth/login",
        json={"email": registered["email"], "password": registered["password"]},
        headers=JSON_HEADERS,
    )
    assert login.status_code == 200
    attach_session_cookie(api_client, login)

    response = api_client.get(
        "/v1/conversations",
        headers=tenant_host_headers(registered["subdomain"]),
    )
    assert response.status_code == 200


def test_f02_t08_logout_on_tenant_subdomain(
    api_client: TestClient,
    db_session: Session,
) -> None:
    registered = register_user(api_client, db_session)
    api_client.cookies.clear()

    login = api_client.post(
        "/api/v1/auth/login",
        json={"email": registered["email"], "password": registered["password"]},
        headers=JSON_HEADERS,
    )
    assert login.status_code == 200
    attach_session_cookie(api_client, login)

    logout = api_client.post(
        "/api/v1/auth/logout",
        headers=tenant_host_headers(registered["subdomain"]),
    )
    assert logout.status_code == 204

    me = api_client.get(
        "/api/v1/auth/me",
        headers=tenant_host_headers(registered["subdomain"]),
    )
    assert me.status_code == 401


def test_f02_unknown_email_same_error_as_wrong_password(
    api_client: TestClient,
    db_session: Session,
) -> None:
    registered = register_user(api_client, db_session)
    api_client.cookies.clear()

    wrong_password = api_client.post(
        "/api/v1/auth/login",
        json={"email": registered["email"], "password": "wrong-password"},
        headers=JSON_HEADERS,
    )
    unknown_email = api_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "password123"},
        headers=JSON_HEADERS,
    )
    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert (
        wrong_password.json()["detail"]["message"]
        == unknown_email.json()["detail"]["message"]
    )


def test_f02_logout_clears_session(
    api_client: TestClient,
    db_session: Session,
) -> None:
    registered = register_user(api_client, db_session)
    api_client.cookies.clear()

    login = api_client.post(
        "/api/v1/auth/login",
        json={"email": registered["email"], "password": registered["password"]},
        headers=JSON_HEADERS,
    )
    assert login.status_code == 200
    attach_session_cookie(api_client, login)

    logout = api_client.post("/api/v1/auth/logout", headers=JSON_HEADERS)
    assert logout.status_code == 204

    me = api_client.get("/api/v1/auth/me", headers=JSON_HEADERS)
    assert me.status_code == 401


def test_login_rejects_tenant_host(api_client: TestClient, db_session: Session) -> None:
    registered = register_user(api_client, db_session)
    response = api_client.post(
        "/api/v1/auth/login",
        json={"email": registered["email"], "password": registered["password"]},
        headers=tenant_host_headers(registered["subdomain"]),
    )
    assert response.status_code == 404
