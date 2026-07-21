from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from rag_api.config import Settings, get_settings
from rag_api.core.security import generate_session_token, hash_session_token
from rag_api.db.models.session import Session
from rag_api.db.models.user import User
from rag_api.repositories.session_repository import SessionRepository
from sqlalchemy.orm import Session as DbSession


@dataclass(frozen=True, slots=True)
class SessionIssueResult:
    session: Session
    token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ValidatedSession:
    user: User
    session: Session


class SessionService:
    def __init__(
        self,
        db_session: DbSession,
        settings: Settings | None = None,
    ) -> None:
        self._db = db_session
        self._settings = settings or get_settings()
        self._repository = SessionRepository(db_session)

    def create_session(self, user_id: UUID) -> SessionIssueResult:
        token = generate_session_token()
        token_hash = hash_session_token(token)
        expires_at = datetime.utcnow() + timedelta(days=self._settings.session_ttl_days)
        session = self._repository.create(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        return SessionIssueResult(session=session, token=token, expires_at=expires_at)

    def validate_session(self, token: str) -> ValidatedSession | None:
        token_hash = hash_session_token(token)
        session = self._repository.find_valid_by_token_hash(token_hash)
        if session is None:
            return None
        user = self._db.get(User, session.user_id)
        if user is None:
            return None
        return ValidatedSession(user=user, session=session)

    def revoke_session(self, token: str) -> bool:
        token_hash = hash_session_token(token)
        session = self._repository.find_by_token_hash(token_hash)
        if session is None or session.revoked_at is not None:
            return False
        self._repository.revoke(session.id)
        return True

    def maybe_slide_expiry(self, session: Session) -> bool:
        threshold_days = self._settings.session_slide_renew_threshold_days
        ttl_days = self._settings.session_ttl_days
        remaining = session.expires_at - datetime.utcnow()
        if remaining >= timedelta(days=threshold_days):
            return False
        new_expires = datetime.utcnow() + timedelta(days=ttl_days)
        self._repository.touch_expires_at(session.id, new_expires)
        return True

    def cookie_max_age_seconds(self) -> int:
        return self._settings.session_ttl_days * 24 * 60 * 60
