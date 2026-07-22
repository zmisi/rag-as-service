"""Document domain constants (F03)."""

from __future__ import annotations

DOC_TAGS = frozenset(
    {"news", "sop", "best_practice", "knowledge_base", "faq"},
)

DOC_STATUSES = frozenset({"draft", "review", "published"})

ALLOWED_EXTENSIONS = frozenset(
    {".txt", ".md", ".pdf", ".doc", ".docx", ".ppt", ".pptx"},
)

MAX_FILE_BYTES = 20 * 1024 * 1024


def is_valid_tag(tag: str) -> bool:
    return tag in DOC_TAGS


def is_allowed_extension(filename: str) -> bool:
    lower = filename.lower()
    for ext in ALLOWED_EXTENSIONS:
        if lower.endswith(ext):
            return True
    return False


def bump_version(current: str) -> str:
    if current == "0.0":
        return "1.0"
    major, _, minor = current.partition(".")
    return f"{major}.{int(minor or 0) + 1}"
