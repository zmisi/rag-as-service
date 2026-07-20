from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from rag_api.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"User(id={self.id!s}, email={self.email!r})"
