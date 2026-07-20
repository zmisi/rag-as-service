"""Shared fixtures for F05 API tests (auth stub + two tenants)."""

from __future__ import annotations

from collections.abc import Generator
from uuid import UUID

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from rag_api.api.dependencies import get_current_user
from rag_api.config import get_settings
from rag_api.db import run_migrations
from rag_api.db.models import Conversation, Message, Tenant, TenantMember, User
from rag_api.db.session import get_db, get_session_factory
from rag_api.main import app


@pytest.fixture(scope="session", autouse=True)
def _migrate() -> None:
    get_settings.cache_clear()
    run_migrations(database_url=get_settings().database_url)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def tenants(db: Session) -> dict:
    """Seed two tenants with owner members; wipe conversation data each test."""
    db.execute(delete(Message))
    db.execute(delete(Conversation))
    db.commit()

    def ensure_tenant(subdomain: str, email: str) -> tuple[Tenant, User]:
        tenant = db.scalar(select(Tenant).where(Tenant.subdomain == subdomain))
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, password_hash="test-hash")
            db.add(user)
            db.flush()
        if tenant is None:
            tenant = Tenant(subdomain=subdomain, display_name=subdomain)
            db.add(tenant)
            db.flush()
        member = db.scalar(
            select(TenantMember).where(
                TenantMember.tenant_id == tenant.id,
                TenantMember.user_id == user.id,
            )
        )
        if member is None:
            db.add(TenantMember(tenant_id=tenant.id, user_id=user.id, role="owner"))
        db.commit()
        db.refresh(tenant)
        db.refresh(user)
        return tenant, user

    tenant_a, user_a = ensure_tenant("tenant-a", "owner-a@example.com")
    tenant_b, user_b = ensure_tenant("tenant-b", "owner-b@example.com")
    return {
        "tenant_a": tenant_a,
        "user_a": user_a,
        "tenant_b": tenant_b,
        "user_b": user_b,
    }


@pytest.fixture
def client(tenants: dict, db: Session) -> Generator[TestClient, None, None]:
    """Single TestClient; auth via X-Test-User-Id (F02 stub for tests)."""

    def _override_user(
        x_test_user_id: str | None = Header(default=None, alias="X-Test-User-Id"),
    ) -> User:
        if not x_test_user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        user = db.get(User, UUID(x_test_user_id))
        if user is None:
            raise HTTPException(status_code=401, detail="Unknown user")
        return user

    def _override_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_a(client: TestClient, tenants: dict) -> TestClient:
    client.headers.update(
        {
            "Host": "tenant-a.lxzxai.com",
            "X-Test-User-Id": str(tenants["user_a"].id),
        }
    )
    return client


@pytest.fixture
def switch_to_b(client: TestClient, tenants: dict):
    def _switch() -> TestClient:
        client.headers.update(
            {
                "Host": "tenant-b.lxzxai.com",
                "X-Test-User-Id": str(tenants["user_b"].id),
            }
        )
        return client

    return _switch
