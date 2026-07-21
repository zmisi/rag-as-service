from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from rag_api.db.engine import get_engine


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


# Back-compat alias used by some F01 helpers.
get_db_session = get_db
