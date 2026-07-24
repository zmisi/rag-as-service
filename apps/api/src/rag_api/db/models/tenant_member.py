from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from rag_api.db.models.base import RAG_SCHEMA, Base, TimestampMixin

ROLE_OWNER = "owner"
MEMBER_ACTIVE = 1
MEMBER_INACTIVE = 0


class TenantMember(TimestampMixin, Base):
    __tablename__ = "tenant_members"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "user_id", name="uk_tenant_members_tenant_id_user_id"
        ),
        UniqueConstraint(
            "tenant_id",
            "member_name",
            name="uk_tenant_members_tenant_id_member_name",
        ),
        CheckConstraint("role IN ('owner')", name="tenant_members_role_chk"),
        CheckConstraint("active IN (0, 1)", name="tenant_members_active_chk"),
    )

    member_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{RAG_SCHEMA}.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(f"{RAG_SCHEMA}.users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_name: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return (
            f"TenantMember(member_id={self.member_id!s}, tenant_id={self.tenant_id!s}, "
            f"user_id={self.user_id!s}, role={self.role!r})"
        )
