import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from rag_api.api import create_app
from rag_api.api.dependencies import get_knowledge_searcher, get_llm_client
from rag_api.api.dependencies.db import get_db
from rag_api.clients.llm import LlmResult, ScriptedLlmClient
from rag_api.config import get_settings
from rag_api.db.migrate import upgrade_head
from rag_api.db.models import (
    AgentRun,
    AgentRunStep,
    Conversation,
    Document,
    DocumentChunk,
    DocumentFile,
    DocumentSection,
    FaqSuggestionStats,
    IndexJob,
    Message,
    Tenant,
    TenantMember,
    User,
)
from rag_api.domain.identity.password import hash_password
from rag_api.indexing.search import FakeKnowledgeSearcher
from tests.helpers import issue_session_for_user, set_client_session_cookie, tenant_host_headers


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
    """F05/F06 style: real commits (services call session.commit())."""
    session = sessionmaker(bind=db_engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def tenants(db: Session) -> dict:
    """Seed pytest-a/b owners; wipe **only those tenants'** data each test.

    Never DELETE across the whole DB — local/dev data shares the same Postgres.
    """
    password_hash = hash_password("password123")

    def ensure_tenant(subdomain: str, email: str) -> tuple[Tenant, User]:
        tenant = db.scalar(select(Tenant).where(Tenant.tenant_name == subdomain))
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                password_hash=password_hash,
                user_name=email.split("@")[0].replace(".", "-")[:32],
            )
            db.add(user)
            db.flush()
        elif user.password_hash != password_hash:
            user.password_hash = password_hash
            db.flush()
        if tenant is None:
            tenant = Tenant(tenant_name=subdomain)
            db.add(tenant)
            db.flush()
        member = db.scalar(
            select(TenantMember).where(
                TenantMember.tenant_id == tenant.tenant_id,
                TenantMember.user_id == user.user_id,
            )
        )
        if member is None:
            db.add(
                TenantMember(
                    tenant_id=tenant.tenant_id,
                    user_id=user.user_id,
                    member_name=user.user_name,
                    role="owner",
                )
            )
        db.commit()
        db.refresh(tenant)
        db.refresh(user)
        return tenant, user

    tenant_a, user_a = ensure_tenant("pytest-a", "owner-pytest-a@example.com")
    tenant_b, user_b = ensure_tenant("pytest-b", "owner-pytest-b@example.com")
    test_tenant_ids = (tenant_a.tenant_id, tenant_b.tenant_id)

    # Scoped wipe: only fixture tenants (preserve other local/dev tenants).
    db.execute(
        delete(AgentRunStep).where(AgentRunStep.tenant_id.in_(test_tenant_ids))
    )
    db.execute(delete(Message).where(Message.tenant_id.in_(test_tenant_ids)))
    db.execute(delete(AgentRun).where(AgentRun.tenant_id.in_(test_tenant_ids)))
    db.execute(
        delete(Conversation).where(Conversation.tenant_id.in_(test_tenant_ids))
    )
    db.execute(
        delete(FaqSuggestionStats).where(
            FaqSuggestionStats.tenant_id.in_(test_tenant_ids)
        )
    )
    db.execute(
        delete(DocumentChunk).where(DocumentChunk.tenant_id.in_(test_tenant_ids))
    )
    db.execute(
        delete(DocumentSection).where(DocumentSection.tenant_id.in_(test_tenant_ids))
    )
    db.execute(delete(IndexJob).where(IndexJob.tenant_id.in_(test_tenant_ids)))
    db.execute(
        delete(DocumentFile).where(DocumentFile.tenant_id.in_(test_tenant_ids))
    )
    db.execute(delete(Document).where(Document.tenant_id.in_(test_tenant_ids)))
    db.commit()

    return {
        "tenant_a": tenant_a,
        "user_a": user_a,
        "tenant_b": tenant_b,
        "user_b": user_b,
    }


@pytest.fixture
def fake_searcher() -> FakeKnowledgeSearcher:
    return FakeKnowledgeSearcher()


@pytest.fixture
def scripted_llm() -> ScriptedLlmClient:
    """Default: endless polite finals so F05 message posts work without QWen."""

    class _Endless(ScriptedLlmClient):
        def complete(self, messages, tools=None):  # type: ignore[no-untyped-def]
            self.calls.append({"messages": messages, "tools": tools})
            if self._script:
                item = self._script.pop(0)
                if isinstance(item, BaseException):
                    raise item
                return item
            return LlmResult(content="好的。")

    return _Endless([])


@pytest.fixture
def client_a(
    app,
    tenants: dict,
    db: Session,
    fake_searcher: FakeKnowledgeSearcher,
    scripted_llm: ScriptedLlmClient,
) -> Generator[TestClient, None, None]:
    """F05/F06 TestClient with cookie auth for pytest-a and mocked LLM/search."""

    def _override_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_llm_client] = lambda: scripted_llm
    app.dependency_overrides[get_knowledge_searcher] = lambda: fake_searcher
    token = issue_session_for_user(db, tenants["user_a"].user_id)
    with TestClient(app) as c:
        set_client_session_cookie(
            c,
            token,
            host=tenant_host_headers("pytest-a")["Host"],
        )
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def switch_to_b(client_a: TestClient, tenants: dict, db: Session):
    def _switch() -> TestClient:
        token = issue_session_for_user(db, tenants["user_b"].user_id)
        set_client_session_cookie(
            client_a,
            token,
            host=tenant_host_headers("pytest-b")["Host"],
        )
        return client_a

    return _switch
