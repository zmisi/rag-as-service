"""Source-file text extraction (F04temp: robust txt; best-effort binary types)."""

from __future__ import annotations

from pathlib import Path


class ParseError(Exception):
    """Raised when a source file cannot be parsed into text."""


def extract_text(filename: str, data: bytes) -> str:
    """Return plain text from uploaded bytes. Raises ParseError on failure."""
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md", ".csv", ""}:
        return _decode_text(data)
    if suffix in {".pdf", ".doc", ".docx", ".ppt", ".pptx"}:
        # F04temp: try utf-8/latin decode for mistyped extensions; else fail clearly.
        try:
            text = _decode_text(data)
            if text.strip():
                return text
        except ParseError:
            pass
        raise ParseError(
            f"F04temp cannot fully parse {suffix}; upload .txt for e2e, "
            "or install full parsers in Spec-approved F04"
        )
    raise ParseError(f"Unsupported file type: {suffix or '(none)'}")


def _decode_text(data: bytes) -> str:
    if not data:
        return ""
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ParseError("Unable to decode text bytes")
