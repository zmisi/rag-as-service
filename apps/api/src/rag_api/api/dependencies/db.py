from collections.abc import Generator

from rag_api.db.session import get_session_factory
from sqlalchemy.orm import Session


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped SQLAlchemy session and close it after the handler."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
