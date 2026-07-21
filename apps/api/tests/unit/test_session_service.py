import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from rag_api.config import Settings
from rag_api.core.security import hash_session_token
from rag_api.repositories.registration_repository import RegistrationRepository
from rag_api.repositories.session_repository import SessionRepository
from rag_api.services.session_service import SessionService


@pytest.mark.integration
def test_create_session_persists_hashed_token(db_session: Session):
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
    from unittest.mock import Mock

    settings = Settings(SESSION_TTL_DAYS=14)
    service = SessionService(db_session=Mock(), settings=settings)
    assert service.cookie_max_age_seconds() == 14 * 24 * 60 * 60


@pytest.mark.integration
def test_validate_session_returns_user(db_session: Session):
    suffix = uuid.uuid4().hex[:8]
    with db_session.begin():
        result = RegistrationRepository(db_session).register_owner(
            email=f"valid-{suffix}@example.com",
            password_hash="hash",
            subdomain=f"valid-{suffix}",
        )
        issue = SessionService(db_session).create_session(result.user.id)

    service = SessionService(db_session)
    validated = service.validate_session(issue.token)
    assert validated is not None
    assert validated.user.id == result.user.id


@pytest.mark.integration
def test_revoke_session_invalidates_token(db_session: Session):
    suffix = uuid.uuid4().hex[:8]
    with db_session.begin():
        result = RegistrationRepository(db_session).register_owner(
            email=f"revoke-{suffix}@example.com",
            password_hash="hash",
            subdomain=f"revoke-{suffix}",
        )
        issue = SessionService(db_session).create_session(result.user.id)

    service = SessionService(db_session)
    assert service.revoke_session(issue.token) is True
    db_session.commit()
    assert service.validate_session(issue.token) is None


@pytest.mark.integration
def test_slide_expiry_extends_session(db_session: Session):
    suffix = uuid.uuid4().hex[:8]
    with db_session.begin():
        result = RegistrationRepository(db_session).register_owner(
            email=f"slide-{suffix}@example.com",
            password_hash="hash",
            subdomain=f"slide-{suffix}",
        )
        issue = SessionService(db_session).create_session(result.user.id)

    repo = SessionRepository(db_session)
    old_expires = datetime.utcnow() + timedelta(days=1)
    repo.touch_expires_at(issue.session.id, old_expires)
    db_session.commit()

    settings = Settings(SESSION_TTL_DAYS=14, SESSION_SLIDE_RENEW_THRESHOLD_DAYS=7)
    service = SessionService(db_session, settings)
    validated = service.validate_session(issue.token)
    assert validated is not None
    assert service.maybe_slide_expiry(validated.session) is True
    db_session.commit()
    db_session.refresh(validated.session)
    assert validated.session.expires_at > old_expires


@pytest.mark.integration
def test_find_valid_by_token_hash(db_session: Session):
    suffix = uuid.uuid4().hex[:8]
    with db_session.begin():
        result = RegistrationRepository(db_session).register_owner(
            email=f"find-{suffix}@example.com",
            password_hash="hash",
            subdomain=f"find-{suffix}",
        )
        issue = SessionService(db_session).create_session(result.user.id)

    repo = SessionRepository(db_session)
    token_hash = hash_session_token(issue.token)
    found = repo.find_valid_by_token_hash(token_hash)
    assert found is not None
    assert found.id == issue.session.id
