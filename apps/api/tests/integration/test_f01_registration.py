import concurrent.futures
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from rag_api.api.dependencies.db import get_db
from rag_api.services.registration_service import RegistrationService
from tests.helpers import APEX_HOST_HEADERS, JSON_HEADERS, unique_subdomain


def _register_payload(email: str | None = None, subdomain: str | None = None):
    suffix = uuid.uuid4().hex[:8]
    return {
        "email": email or f"user-{suffix}@example.com",
        "password": "password123",
        "subdomain": subdomain or unique_subdomain("acme"),
    }


def _tenant_count(db_session: Session, subdomain: str) -> int:
    return db_session.execute(
        text("SELECT count(*) FROM rag_service.tenants WHERE subdomain = :subdomain"),
        {"subdomain": subdomain},
    ).scalar_one()


def _owner_count(db_session: Session, subdomain: str) -> int:
    return db_session.execute(
        text(
            """
            SELECT count(*)
            FROM rag_service.tenant_members tm
            JOIN rag_service.tenants t ON t.id = tm.tenant_id
            WHERE t.subdomain = :subdomain AND tm.role = 'owner'
            """
        ),
        {"subdomain": subdomain},
    ).scalar_one()


@pytest.mark.integration
def test_f01_t01_successful_registration(api_client, db_session):
    payload = _register_payload()
    response = api_client.post(
        "/api/v1/auth/register",
        json=payload,
        headers=JSON_HEADERS,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["subdomain"] == payload["subdomain"]
    assert _tenant_count(db_session, payload["subdomain"]) == 1
    assert _owner_count(db_session, payload["subdomain"]) == 1
    assert api_client.cookies.get("pb_session")


@pytest.mark.integration
def test_f01_t02_subdomain_normalized_to_lowercase(api_client, db_session):
    suffix = uuid.uuid4().hex[:6]
    subdomain = f"Acme-{suffix}"[:32]
    payload = _register_payload(subdomain=subdomain)
    response = api_client.post(
        "/api/v1/auth/register",
        json=payload,
        headers=JSON_HEADERS,
    )
    assert response.status_code == 201
    stored = subdomain.lower()
    assert response.json()["subdomain"] == stored
    assert _tenant_count(db_session, stored) == 1


@pytest.mark.integration
def test_f01_t03_subdomain_too_short(api_client, db_session):
    payload = _register_payload(subdomain="ab")
    response = api_client.post(
        "/api/v1/auth/register",
        json=payload,
        headers=JSON_HEADERS,
    )
    assert response.status_code == 400
    assert _tenant_count(db_session, "ab") == 0


@pytest.mark.integration
def test_f01_t04_reserved_subdomain(api_client, db_session):
    payload = _register_payload(subdomain="admin")
    response = api_client.post(
        "/api/v1/auth/register",
        json=payload,
        headers=JSON_HEADERS,
    )
    assert response.status_code == 400
    assert _tenant_count(db_session, "admin") == 0


@pytest.mark.integration
def test_f01_t05_subdomain_already_taken(api_client, db_session):
    payload = _register_payload()
    first = api_client.post(
        "/api/v1/auth/register",
        json=payload,
        headers=JSON_HEADERS,
    )
    assert first.status_code == 201

    second_payload = _register_payload(subdomain=payload["subdomain"])
    second = api_client.post(
        "/api/v1/auth/register",
        json=second_payload,
        headers=JSON_HEADERS,
    )
    assert second.status_code == 409
    assert _tenant_count(db_session, payload["subdomain"]) == 1


@pytest.mark.integration
def test_f01_t06_email_already_registered(api_client, db_session):
    payload = _register_payload()
    first = api_client.post(
        "/api/v1/auth/register",
        json=payload,
        headers=JSON_HEADERS,
    )
    assert first.status_code == 201

    second_payload = _register_payload(email=payload["email"])
    second = api_client.post(
        "/api/v1/auth/register",
        json=second_payload,
        headers=JSON_HEADERS,
    )
    assert second.status_code == 409
    assert _tenant_count(db_session, second_payload["subdomain"]) == 0


@pytest.mark.integration
def test_f01_t08_concurrent_subdomain_registration(db_engine: Engine):
    subdomain = unique_subdomain("race")
    barrier = concurrent.futures.Barrier(2)
    results: list[bool] = []

    def attempt(index: int) -> None:
        connection = db_engine.connect()
        transaction = connection.begin()
        session = sessionmaker(bind=connection, expire_on_commit=False)()
        try:
            barrier.wait(timeout=5)
            service = RegistrationService(session)
            service.register(
                email=f"race-{index}-{uuid.uuid4().hex[:8]}@example.com",
                password="password123",
                subdomain=subdomain,
            )
            transaction.commit()
            results.append(True)
        except Exception:
            transaction.rollback()
            results.append(False)
        finally:
            session.close()
            connection.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(attempt, i) for i in range(2)]
        concurrent.futures.wait(futures)

    assert results.count(True) == 1
    assert results.count(False) == 1

    with db_engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM rag_service.tenants WHERE subdomain = :subdomain"),
            {"subdomain": subdomain},
        ).scalar_one()
        assert count == 1

    with db_engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM rag_service.tenant_members
                WHERE tenant_id IN (
                  SELECT id FROM rag_service.tenants WHERE subdomain = :subdomain
                )
                """
            ),
            {"subdomain": subdomain},
        )
        conn.execute(
            text("DELETE FROM rag_service.tenants WHERE subdomain = :subdomain"),
            {"subdomain": subdomain},
        )
        conn.execute(
            text(
                """
                DELETE FROM rag_service.users
                WHERE email LIKE 'race-%@example.com'
                """
            ),
        )


@pytest.mark.integration
def test_register_rejects_non_apex_host(api_client):
    payload = _register_payload()
    response = api_client.post(
        "/api/v1/auth/register",
        json=payload,
        headers={"Host": "tenant.lxzxai.com", "Accept": "application/json"},
    )
    assert response.status_code == 404


@pytest.mark.integration
def test_register_redirect_for_html_accept(api_client, db_session):
    payload = _register_payload()
    response = api_client.post(
        "/api/v1/auth/register",
        json=payload,
        headers={**APEX_HOST_HEADERS, "Accept": "text/html"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == f"https://{payload['subdomain']}.lxzxai.com/admin"
    assert "domain=.lxzxai.com" in response.headers.get("set-cookie", "").lower()
