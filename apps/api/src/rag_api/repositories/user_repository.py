from rag_api.db.models.user import USER_ACTIVE, User
from sqlalchemy import select
from sqlalchemy.orm import Session


class UserRepository:
    """Persistence for user account rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_email(self, email: str) -> User | None:
        """Find user by email, or None if not registered."""
        stmt = select(User).where(User.email == email)
        return self._session.scalar(stmt)

    def find_by_user_name(self, user_name: str) -> User | None:
        """Find user by ``user_name``, or None if not taken."""
        stmt = select(User).where(User.user_name == user_name)
        return self._session.scalar(stmt)

    def create(
        self,
        email: str,
        password_hash: str,
        user_name: str,
        *,
        active: int = USER_ACTIVE,
    ) -> User:
        """Insert a new user account and return the flushed row."""
        user = User(
            email=email,
            password_hash=password_hash,
            user_name=user_name,
            active=active,
        )
        self._session.add(user)
        self._session.flush()
        return user
