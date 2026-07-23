"""Document domain constants (F03 / F07)."""

from __future__ import annotations

import hashlib

DOC_TAGS = frozenset(
    {"news", "sop", "best_practice", "knowledge_base", "faq"},
)

PUBLISH_STATUSES = frozenset({"draft", "review", "published"})
DOC_STATUSES = PUBLISH_STATUSES  # API / legacy alias

INDEX_STATUSES = frozenset({"pending", "processing", "ready", "failed"})

CHUNK_TYPES = frozenset({"text", "table", "mixed"})

# Phase 1: OOXML only for Word/PPT; .md as plain text. Legacy .doc / .ppt are rejected.
ALLOWED_EXTENSIONS = frozenset({".txt", ".md", ".pdf", ".docx", ".pptx"})

LEGACY_EXTENSIONS = frozenset({".doc", ".ppt"})

MAX_FILE_BYTES = 20 * 1024 * 1024

UNSUPPORTED_FILE_TYPE_MESSAGE = (
    "Unsupported file type. Allowed: .txt, .md, .pdf, .docx, .pptx"
)

LEGACY_FILE_TYPE_MESSAGE = (
    "Legacy .doc / .ppt are not supported. "
    "Please re-save as .docx / .pptx and upload again."
)


def is_valid_tag(tag: str) -> bool:
    return tag in DOC_TAGS


def _matched_extension(filename: str, extensions: frozenset[str]) -> str | None:
    lower = filename.lower()
    # Longest first so .docx is not confused with a prefix of itself.
    for ext in sorted(extensions, key=len, reverse=True):
        if lower.endswith(ext):
            return ext
    return None


def is_allowed_extension(filename: str) -> bool:
    return _matched_extension(filename, ALLOWED_EXTENSIONS) is not None


def is_legacy_extension(filename: str) -> bool:
    """True for .doc / .ppt only (not .docx / .pptx)."""
    lower = filename.lower()
    if lower.endswith(".docx") or lower.endswith(".pptx"):
        return False
    return _matched_extension(filename, LEGACY_EXTENSIONS) is not None


def file_type_reject_message(filename: str) -> str:
    if is_legacy_extension(filename):
        return LEGACY_FILE_TYPE_MESSAGE
    return UNSUPPORTED_FILE_TYPE_MESSAGE


def next_version(current: int | None) -> int:
    """Next integer version; unset / 0 → 1."""
    if current is None or current <= 0:
        return 1
    return int(current) + 1


def bump_version(current: str | int | None) -> str:
    """Legacy wrapper: returns str of next_version for older callers/tests."""
    if isinstance(current, str):
        if current in ("", "0.0", "0"):
            n = 0
        else:
            major, _, _ = current.partition(".")
            try:
                n = int(major or 0)
            except ValueError:
                n = 0
        return str(next_version(n))
    return str(next_version(current))


def format_version_display(n: int) -> str:
    return f"v{int(n)}"


def content_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
