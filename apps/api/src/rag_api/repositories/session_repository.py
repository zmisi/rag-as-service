from datetime import datetime
from uuid import UUID

from rag_api.db.models.session import Session
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession


class SessionRepository:
    def __init__(self, session: DbSession) -> None:
        self._session = session

    def create(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> Session:
        row = Session(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def find_by_token_hash(self, token_hash: str) -> Session | None:
        stmt = select(Session).where(Session.token_hash == token_hash)
        return self._session.scalar(stmt)

    def find_valid_by_token_hash(self, token_hash: str) -> Session | None:
        now = datetime.utcnow()
        stmt = select(Session).where(
            Session.token_hash == token_hash,
            Session.revoked_at.is_(None),
            Session.expires_at > now,
        )
        return self._session.scalar(stmt)

    def revoke(self, session_id: UUID) -> None:
        row = self._session.get(Session, session_id)
        if row is None:
            return
        row.revoked_at = datetime.utcnow()
        self._session.flush()

    def touch_expires_at(self, session_id: UUID, expires_at: datetime) -> None:
        row = self._session.get(Session, session_id)
        if row is None:
            return
        row.expires_at = expires_at
        self._session.flush()
