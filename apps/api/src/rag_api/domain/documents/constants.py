"""Document domain constants (F03 / F07)."""

from __future__ import annotations

import hashlib
from uuid import UUID

DOC_TAGS = frozenset(
    {"news", "sop", "best_practice", "knowledge_base", "faq"},
)

PUBLISH_STATUSES = frozenset({"draft", "review", "published"})
DOC_STATUSES = PUBLISH_STATUSES  # API / legacy alias

INGEST_STATUSES = frozenset({"pending", "processing", "ready", "failed"})
INDEX_STATUSES = INGEST_STATUSES  # deprecated alias

CHUNK_TYPES = frozenset({"text", "table", "mixed"})

# F08: text/PDF + OOXML. Legacy binary Office rejected.
ALLOWED_EXTENSIONS = frozenset({".txt", ".md", ".pdf", ".docx", ".pptx", ".xlsx"})

LEGACY_EXTENSIONS = frozenset({".doc", ".ppt", ".xls"})

MAX_FILE_BYTES = 20 * 1024 * 1024

UNSUPPORTED_FILE_TYPE_MESSAGE = (
    "Unsupported file type. Allowed: .txt, .md, .pdf, .docx, .pptx, .xlsx"
)

LEGACY_FILE_TYPE_MESSAGE = (
    "Legacy .doc / .ppt / .xls are not supported. "
    "Please re-save as .docx / .pptx / .xlsx and upload again."
)

FILE_TYPE_MISMATCH_MESSAGE = (
    "File content does not match the declared extension "
    "(magic-byte check failed)."
)

# Same-tenant content dedup at publish (knowledge-base reject).
# Other doc_group with same file_content_sha256 + published+ready → HTTP 409.
ERROR_CODE_DUPLICATE_CONTENT_SHA256 = "duplicate_content_sha256"


def duplicate_content_conflict_detail(
    *,
    existing_document_id: UUID | str,
    existing_title: str | None,
) -> dict[str, str]:
    title = (existing_title or "").strip() or "未命名"
    return {
        "code": ERROR_CODE_DUPLICATE_CONTENT_SHA256,
        "message": (
            f"知识库中已存在相同内容的文档「{title}」，"
            "请打开原文档或更换文件后再发布。"
        ),
        "existing_document_id": str(existing_document_id),
        "existing_title": title,
    }


# Legacy aliases (historical clone-path jobs / responses). Prefer ERROR_CODE_*.
WARNING_CODE_DUPLICATE_CONTENT_SHA256 = ERROR_CODE_DUPLICATE_CONTENT_SHA256
WARNING_DUPLICATE_CONTENT_SHA256 = (
    "知识库中已存在相同内容的文档，发布已拒绝；请打开原文档或更换文件。"
)
INGEST_JOB_ERROR_DUPLICATE_CONTENT_SHA256 = (
    "rejected: duplicate content_sha256 in tenant"
)
# Deprecated alias (one release).
INDEX_JOB_ERROR_DUPLICATE_CONTENT_SHA256 = INGEST_JOB_ERROR_DUPLICATE_CONTENT_SHA256


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
    """True for .doc / .ppt / .xls only (not .docx / .pptx / .xlsx)."""
    lower = filename.lower()
    if lower.endswith((".docx", ".pptx", ".xlsx")):
        return False
    return _matched_extension(filename, LEGACY_EXTENSIONS) is not None


def file_type_reject_message(filename: str) -> str:
    if is_legacy_extension(filename):
        return LEGACY_FILE_TYPE_MESSAGE
    return UNSUPPORTED_FILE_TYPE_MESSAGE


def matched_allowed_extension(filename: str) -> str | None:
    return _matched_extension(filename, ALLOWED_EXTENSIONS)


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
