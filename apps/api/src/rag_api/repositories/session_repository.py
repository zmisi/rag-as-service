from datetime import datetime
from uuid import UUID

from rag_api.db.models.session import Session
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
