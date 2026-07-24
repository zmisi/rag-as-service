from uuid import UUID

from sqlalchemy import Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from rag_api.db.models.base import Base, TimestampMixin

USER_ACTIVE = 1
USER_INACTIVE = 0


class User(TimestampMixin, Base):
    __tablename__ = "users"

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )

    def __repr__(self) -> str:
        return f"User(user_id={self.user_id!s}, email={self.email!r})"
