import uuid
from datetime import datetime

from sqlalchemy import MetaData, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP, Text, Uuid

RAG_SCHEMA = "rag_service"

metadata = MetaData(schema=RAG_SCHEMA)


class Base(DeclarativeBase):
    metadata = metadata


class TimestampMixin:
    create_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=text("now()"),
        nullable=False,
    )
    update_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=text("now()"),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
