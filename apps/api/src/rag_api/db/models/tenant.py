from uuid import UUID

from sqlalchemy import CheckConstraint, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from rag_api.db.models.base import Base, TimestampMixin

TENANT_STATUS_ACTIVE = "active"
TENANT_STATUS_SUSPENDED = "suspended"
CHARGE_MODE_FREE = "free"
CHARGE_MODE_STANDARD = "standard"


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            "char_length(tenant_name) BETWEEN 3 AND 32",
            name="tenants_tenant_name_length_chk",
        ),
        CheckConstraint(
            "tenant_name ~ '^[a-z0-9]([a-z0-9-]*[a-z0-9])?$'",
            name="tenants_tenant_name_format_chk",
        ),
        CheckConstraint(
            "status IN ('active', 'suspended')",
            name="tenants_status_chk",
        ),
        CheckConstraint(
            "charge_mode IN ('free', 'standard')",
            name="tenants_charge_mode_chk",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'active'")
    )
    charge_mode: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'free'")
    )

    def __repr__(self) -> str:
        return (
            f"Tenant(tenant_id={self.tenant_id!s}, tenant_name={self.tenant_name!r})"
        )
