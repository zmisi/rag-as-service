import re
import uuid
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rag_api.config import get_settings
from rag_api.db.models import User
from rag_api.domain.identity.password import hash_password
from rag_api.services.session_service import SessionService

APEX_HOST_HEADERS = {"Host": "lxzxai.com"}
JSON_HEADERS = {**APEX_HOST_HEADERS, "Accept": "application/json"}

_SESSION_COOKIE_RE = re.compile(r"pb_session=([^;]+)")


def unique_subdomain(prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    value = f"{prefix}-{suffix}".lower()
    return value[:32]


def tenant_host_headers(subdomain: str) -> dict[str, str]:
    return {"Host": f"{subdomain}.lxzxai.com", "Accept": "application/json"}


def issue_session_for_user(db: Session, user_id: UUID) -> str:
    service = SessionService(db, get_settings())
    issue = service.create_session(user_id)
    db.commit()
    return issue.token


def set_client_session_cookie(
    client: TestClient,
    token: str,
    *,
    host: str | None = None,
) -> TestClient:
    settings = get_settings()
    # TestClient uses host ``testserver``; omit Domain so cookies are sent.
    client.cookies.set(settings.session_cookie_name, token)
    if host:
        client.headers.update({"Host": host})
    return client


def attach_session_cookie(client: TestClient, response) -> TestClient:
    """Copy session token from Set-Cookie onto TestClient (testserver-safe)."""
    settings = get_settings()
    token = client.cookies.get(settings.session_cookie_name)
    if not token:
        header = response.headers.get("set-cookie", "")
        match = _SESSION_COOKIE_RE.search(header)
        if match:
            token = match.group(1)
    if token:
        client.cookies.set(settings.session_cookie_name, token)
    return client


def register_user(
    client: TestClient,
    db: Session,
    *,
    email: str | None = None,
    password: str = "password123",
    subdomain: str | None = None,
) -> dict:
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "email": email or f"user-{suffix}@example.com",
        "password": password,
        "subdomain": subdomain or unique_subdomain("login"),
    }
    response = client.post(
        "/api/v1/auth/register",
        json=payload,
        headers=JSON_HEADERS,
    )
    assert response.status_code == 201, response.text
    return {**payload, "response": response.json()}
