import os
from collections.abc import Generator
from uuid import UUID

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from rag_api.api import create_app
from rag_api.api.dependencies import get_current_user
from rag_api.api.dependencies.db import get_db
from rag_api.config import get_settings
from rag_api.db.migrate import upgrade_head
from rag_api.db.models import Conversation, Message, Tenant, TenantMember, User


def _database_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def db_engine() -> Engine:
    url = _database_url()
    if not url:
        pytest.skip("DATABASE_URL or TEST_DATABASE_URL not set")

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"options": "-csearch_path=rag_service,public"},
    )
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available: {exc}")

    get_settings.cache_clear()
    upgrade_head()
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Session:
    """F01-style: outer transaction rolled back after each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, expire_on_commit=False)()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def api_client(app, db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def db(db_engine: Engine) -> Generator[Session, None, None]:
    """F05-style: real commits (services call session.commit())."""
    session = sessionmaker(bind=db_engine, expire_on_commit=False)()
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
def client_a(app, tenants: dict, db: Session) -> Generator[TestClient, None, None]:
    """F05 TestClient; auth via X-Test-User-Id stub."""

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
        c.headers.update(
            {
                "Host": "tenant-a.lxzxai.com",
                "X-Test-User-Id": str(tenants["user_a"].id),
            }
        )
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def switch_to_b(client_a: TestClient, tenants: dict):
    def _switch() -> TestClient:
        client_a.headers.update(
            {
                "Host": "tenant-b.lxzxai.com",
                "X-Test-User-Id": str(tenants["user_b"].id),
            }
        )
        return client_a

    return _switch
