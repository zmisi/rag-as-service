from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from rag_api.db.models.base import RAG_SCHEMA, Base, TimestampMixin, UUIDPrimaryKeyMixin

ROLE_OWNER = "owner"


class TenantMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenant_members"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="tenant_members_tenant_user_key"),
        CheckConstraint("role IN ('owner')", name="tenant_members_role_chk"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{RAG_SCHEMA}.tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{RAG_SCHEMA}.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return (
            f"TenantMember(id={self.id!s}, tenant_id={self.tenant_id!s}, "
            f"user_id={self.user_id!s}, role={self.role!r})"
        )
