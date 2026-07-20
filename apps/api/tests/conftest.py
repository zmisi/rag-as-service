import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from rag_api.api import create_app
from rag_api.api.dependencies.db import get_db
from rag_api.db.migrate import upgrade_head


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

    upgrade_head()
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Session:
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
