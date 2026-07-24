from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from rag_api.db.models.base import RAG_SCHEMA, Base, TimestampMixin, UUIDPrimaryKeyMixin

STATUS_ACTIVE = "active"
STATUS_REVOKED = "revoked"


class WidgetSiteKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "widget_site_keys"

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{RAG_SCHEMA}.tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    public_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default=STATUS_ACTIVE)
    allowed_origins: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'"),
    )
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
