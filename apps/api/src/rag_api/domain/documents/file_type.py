"""Filename extension + magic-byte file type gates (F08)."""

from __future__ import annotations

import io
import zipfile

from rag_api.domain.documents.constants import (
    FILE_TYPE_MISMATCH_MESSAGE,
    file_type_reject_message,
    is_allowed_extension,
    matched_allowed_extension,
)

_ZIP_LOCAL = b"PK\x03\x04"
_ZIP_EMPTY = b"PK\x05\x06"
_PDF_MAGIC = b"%PDF"
_TEXT_PROBE_BYTES = 8192

_OOXML_PART_PREFIX = {
    ".docx": "word/",
    ".pptx": "ppt/",
    ".xlsx": "xl/",
}


class FileTypeError(ValueError):
    """Raised when extension or magic-byte validation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _is_zip_magic(data: bytes) -> bool:
    return data.startswith(_ZIP_LOCAL) or data.startswith(_ZIP_EMPTY)


def _zip_has_prefix(data: bytes, prefix: str) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return any(name.startswith(prefix) for name in zf.namelist())
    except zipfile.BadZipFile:
        return False


def validate_file_type(filename: str, data: bytes) -> str:
    """Validate extension allowlist + magic bytes.

    Returns the matched lowercase extension (e.g. ``.docx``).
    Raises ``FileTypeError`` on failure (do not reclassify by magic).
    """
    if not is_allowed_extension(filename):
        raise FileTypeError(file_type_reject_message(filename))

    ext = matched_allowed_extension(filename)
    assert ext is not None

    if ext == ".pdf":
        if not data.startswith(_PDF_MAGIC):
            raise FileTypeError(FILE_TYPE_MISMATCH_MESSAGE)
        return ext

    if ext in _OOXML_PART_PREFIX:
        if not _is_zip_magic(data):
            raise FileTypeError(FILE_TYPE_MISMATCH_MESSAGE)
        prefix = _OOXML_PART_PREFIX[ext]
        if not _zip_has_prefix(data, prefix):
            raise FileTypeError(FILE_TYPE_MISMATCH_MESSAGE)
        return ext

    if ext in {".txt", ".md"}:
        probe = data[:_TEXT_PROBE_BYTES]
        if b"\x00" in probe:
            raise FileTypeError(FILE_TYPE_MISMATCH_MESSAGE)
        return ext

    raise FileTypeError(FILE_TYPE_MISMATCH_MESSAGE)
