from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rag_api.db.models import User
from tests.helpers import JSON_HEADERS, attach_session_cookie, register_user, tenant_host_headers

pytestmark = pytest.mark.integration


def test_create_member_returns_temporary_password_and_forces_password_change(
    api_client: TestClient,
    db_session: Session,
) -> None:
    owner = register_user(api_client, db_session)

    create = api_client.post(
        "/v1/members",
        json={
            "member_name": "张三",
            "email": "member1@example.com",
            "role": "member",
        },
        headers=tenant_host_headers(owner["subdomain"]),
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["temporary_password"]
    assert body["must_change_password"] is True

    user = db_session.query(User).filter(User.email == "member1@example.com").one()
    assert user.must_change_password is True

    api_client.cookies.clear()
    login = api_client.post(
        "/api/v1/auth/login",
        json={
            "email": "member1@example.com",
            "password": body["temporary_password"],
        },
        headers=JSON_HEADERS,
    )
    assert login.status_code == 200, login.text
    login_body = login.json()
    assert login_body["must_change_password"] is True
    assert "/change-password" in login_body["change_password_url"]


def test_change_password_clears_first_login_flag(
    api_client: TestClient,
    db_session: Session,
) -> None:
    owner = register_user(api_client, db_session)
    create = api_client.post(
        "/v1/members",
        json={
            "member_name": "李四",
            "email": "member2@example.com",
            "role": "admin",
        },
        headers=tenant_host_headers(owner["subdomain"]),
    )
    temp_password = create.json()["temporary_password"]

    api_client.cookies.clear()
    login = api_client.post(
        "/api/v1/auth/login",
        json={"email": "member2@example.com", "password": temp_password},
        headers=JSON_HEADERS,
    )
    attach_session_cookie(api_client, login)

    change = api_client.post(
        "/api/v1/auth/change-password",
        json={"new_password": "new-password-123"},
        headers=JSON_HEADERS,
    )
    assert change.status_code == 204

    user = db_session.query(User).filter(User.email == "member2@example.com").one()
    db_session.refresh(user)
    assert user.must_change_password is False

    api_client.cookies.clear()
    old_login = api_client.post(
        "/api/v1/auth/login",
        json={"email": "member2@example.com", "password": temp_password},
        headers=JSON_HEADERS,
    )
    assert old_login.status_code == 401

    new_login = api_client.post(
        "/api/v1/auth/login",
        json={"email": "member2@example.com", "password": "new-password-123"},
        headers=JSON_HEADERS,
    )
    assert new_login.status_code == 200
    assert new_login.json()["must_change_password"] is False
