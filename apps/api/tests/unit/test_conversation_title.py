"""Unit tests for conversation title helpers."""

from __future__ import annotations

from rag_api.services.conversations import (
    AUTO_TITLE_MAX_LEN,
    DEFAULT_TITLE,
    derive_title_from_message,
)


def test_derive_title_from_message_short() -> None:
    assert derive_title_from_message("退货政策是什么？") == "退货政策是什么？"


def test_derive_title_from_message_collapses_whitespace() -> None:
    assert derive_title_from_message("hello\n\nit is a test") == "hello it is a test"


def test_derive_title_from_message_truncates_long() -> None:
    long_text = "问" * (AUTO_TITLE_MAX_LEN + 10)
    title = derive_title_from_message(long_text)
    assert len(title) == AUTO_TITLE_MAX_LEN
    assert title.endswith("…")


def test_derive_title_from_message_empty_falls_back() -> None:
    assert derive_title_from_message("   \n  ") == DEFAULT_TITLE
