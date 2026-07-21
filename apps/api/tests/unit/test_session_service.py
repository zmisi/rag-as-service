import uuid
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from rag_api.services.session_service import SessionService


@pytest.mark.integration
def test_create_session_persists_hashed_token(db_session: Session):
    from rag_api.repositories.registration_repository import RegistrationRepository

    suffix = uuid.uuid4().hex[:8]
    with db_session.begin():
        result = RegistrationRepository(db_session).register_owner(
            email=f"session-{suffix}@example.com",
            password_hash="hash",
            subdomain=f"sess-{suffix}",
        )
        issue = SessionService(db_session).create_session(result.user.id)

    assert issue.token
    assert issue.session.user_id == result.user.id
    assert issue.session.token_hash != issue.token


def test_cookie_max_age_uses_settings():
    from rag_api.config import Settings

    settings = Settings(SESSION_TTL_DAYS=14)
    service = SessionService(db_session=Mock(), settings=settings)
    assert service.cookie_max_age_seconds() == 14 * 24 * 60 * 60
