"""Unit tests for integer document version helpers (F07)."""

from __future__ import annotations

from rag_api.domain.documents.constants import (
    bump_version,
    format_version_display,
    next_version,
)


def test_next_version_from_none_and_zero() -> None:
    assert next_version(None) == 1
    assert next_version(0) == 1
    assert next_version(-1) == 1


def test_next_version_increments() -> None:
    assert next_version(1) == 2
    assert next_version(9) == 10


def test_bump_version_legacy_string() -> None:
    assert bump_version("1.0") == "2"
    assert bump_version("1.1") == "2"
    assert bump_version("") == "1"
    assert bump_version(None) == "1"
    assert bump_version(3) == "4"


def test_format_version_display() -> None:
    assert format_version_display(1) == "v1"
    assert format_version_display(12) == "v12"
