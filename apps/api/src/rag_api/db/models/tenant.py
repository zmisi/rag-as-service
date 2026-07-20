from sqlalchemy import CheckConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from rag_api.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            "char_length(subdomain) BETWEEN 3 AND 32",
            name="tenants_subdomain_length_chk",
        ),
        CheckConstraint(
            "subdomain ~ '^[a-z0-9]([a-z0-9-]*[a-z0-9])?$'",
            name="tenants_subdomain_format_chk",
        ),
    )

    subdomain: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"Tenant(id={self.id!s}, subdomain={self.subdomain!r})"
