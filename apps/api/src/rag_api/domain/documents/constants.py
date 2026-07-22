"""Document domain constants (F03)."""

from __future__ import annotations

DOC_TAGS = frozenset(
    {"news", "sop", "best_practice", "knowledge_base", "faq"},
)

DOC_STATUSES = frozenset({"draft", "review", "published"})

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


def bump_version(current: str) -> str:
    if current == "0.0":
        return "1.0"
    major, _, minor = current.partition(".")
    return f"{major}.{int(minor or 0) + 1}"
