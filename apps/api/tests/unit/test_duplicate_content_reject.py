"""Unit tests for publish-time content dedup (409 reject)."""

from __future__ import annotations

from rag_api.domain.documents.constants import (
    ERROR_CODE_DUPLICATE_CONTENT_SHA256,
    duplicate_content_conflict_detail,
)


def test_duplicate_content_conflict_detail_shape() -> None:
    detail = duplicate_content_conflict_detail(
        existing_document_id="11111111-1111-1111-1111-111111111111",
        existing_title="退货政策",
    )
    assert detail["code"] == ERROR_CODE_DUPLICATE_CONTENT_SHA256
    assert detail["existing_document_id"] == "11111111-1111-1111-1111-111111111111"
    assert detail["existing_title"] == "退货政策"
    assert "退货政策" in detail["message"]


def test_duplicate_content_conflict_detail_empty_title() -> None:
    detail = duplicate_content_conflict_detail(
        existing_document_id="x",
        existing_title="  ",
    )
    assert detail["existing_title"] == "未命名"
    assert "未命名" in detail["message"]
