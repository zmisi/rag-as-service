"""Pydantic schemas for F13 Portal FAQ suggestions."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class FaqSuggestionOut(BaseModel):
    document_group_id: UUID
    document_id: UUID
    question: str
    click_count: int
    hot: bool


class FaqClickOut(BaseModel):
    document_group_id: UUID
    document_id: UUID
    question: str
    click_count: int
