from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from rag_api.db.models.base import RAG_SCHEMA, Base, TimestampMixin, UUIDPrimaryKeyMixin

STATUS_ACTIVE = "active"
STATUS_REVOKED = "revoked"
SECRET_PREFIX = "rk_live_"


class ApiKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default=STATUS_ACTIVE)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
