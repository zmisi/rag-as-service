"""Pydantic schemas for F03 documents."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    version: str
    create_at: datetime
    update_at: datetime


class DocumentSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    title: str
    tag: str
    status: str
    version: str
    create_at: datetime
    update_at: datetime


class DocumentDetailOut(DocumentSummaryOut):
    files: list[DocumentFileOut] = Field(default_factory=list)


class DocumentSaveRequest(BaseModel):
    title: str | None = None
    tag: str | None = None


class IndexJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    error: str | None = None
    attempt_count: int
    create_at: datetime
    update_at: datetime
