from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from rag_api.config import Settings, get_settings
from rag_api.core.security import generate_session_token, hash_session_token
from rag_api.db.models.session import Session
from rag_api.repositories.session_repository import SessionRepository
from sqlalchemy.orm import Session as DbSession


@dataclass(frozen=True, slots=True)
class SessionIssueResult:
    session: Session
    token: str
    expires_at: datetime


class SessionService:
    def __init__(
        self,
        db_session: DbSession,
        settings: Settings | None = None,
    ) -> None:
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

    def cookie_max_age_seconds(self) -> int:
        return self._settings.session_ttl_days * 24 * 60 * 60
