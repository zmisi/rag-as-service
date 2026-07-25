"""Text chunking with fixed token budget (char approximation).

Table-aware: when over budget, split at Markdown table boundaries; keep
tables intact (or header+row groups if a single table is huge); sliding
window applies to prose only (F04-T23).
"""

from __future__ import annotations

import re
from typing import Literal

from rag_api.indexing.constants import (
    CHARS_PER_TOKEN,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_TARGET_TOKENS,
)

_TABLE_ROW_RE = re.compile(r"^\|.+\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\|?\s*:?-{3,}")

SegmentKind = Literal["prose", "table"]


def _is_table_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if _TABLE_ROW_RE.match(s):
        return True
    return bool(_TABLE_SEP_RE.match(s) and "|" in s)


def _split_prose_and_tables(text: str) -> list[tuple[SegmentKind, str]]:
    """Split into ordered prose / Markdown-table segments."""
    lines = text.splitlines()
    segments: list[tuple[SegmentKind, str]] = []
    buf: list[str] = []
    mode: SegmentKind | None = None

    def flush() -> None:
        nonlocal buf, mode
        if mode is None or not buf:
            buf = []
            mode = None
            return
        body = "\n".join(buf).strip()
        if body:
            segments.append((mode, body))
        buf = []
        mode = None

    for line in lines:
        is_table = _is_table_line(line)
        kind: SegmentKind = "table" if is_table else "prose"
        if mode is None:
            mode = kind
            buf = [line]
            continue
        if kind == mode:
            buf.append(line)
            continue
        flush()
        mode = kind
        buf = [line]
    flush()
    return segments


def _sliding_window(
    text: str,
    *,
    target_chars: int,
    overlap_chars: int,
) -> list[str]:
    normalized = (text or "").strip()
    if not normalized:
        return []
    if len(normalized) <= target_chars:
        return [normalized]

    chunks: list[str] = []
    start = 0
    n = len(normalized)
    while start < n:
        end = min(n, start + target_chars)
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(0, end - overlap_chars)
        if start >= end:
            start = end
    return chunks


def _is_separator_row(line: str) -> bool:
    s = line.strip()
    return bool(_TABLE_SEP_RE.match(s) or (s.startswith("|") and "---" in s))


def _chunk_table(table: str, *, target_chars: int) -> list[str]:
    """Prefer whole table; if huge, split data rows keeping header+sep."""
    normalized = (table or "").strip()
    if not normalized:
        return []
    if len(normalized) <= target_chars:
        return [normalized]

    lines = normalized.splitlines()
    if len(lines) <= 2:
        return [normalized]

    if _is_separator_row(lines[1]):
        header = lines[:2]
        data_rows = lines[2:]
    else:
        header = lines[:1]
        data_rows = lines[1:]

    if not data_rows:
        return [normalized]

    chunks: list[str] = []
    batch: list[str] = []
    for row in data_rows:
        candidate_lines = header + batch + [row]
        candidate = "\n".join(candidate_lines)
        if batch and len(candidate) > target_chars:
            chunks.append("\n".join(header + batch))
            batch = [row]
        else:
            batch.append(row)
    if batch:
        chunks.append("\n".join(header + batch))
    return chunks


def chunk_text(
    text: str,
    *,
    target_tokens: int = CHUNK_TARGET_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> list[str]:
    """Split text into overlapping chunks. Empty / whitespace → [].

    Under budget → single leaf (may be mixed prose+table).
    Over budget → split at table boundaries; tables kept whole (or
    header+row groups); sliding window only on prose.
    """
    normalized = (text or "").strip()
    if not normalized:
        return []

    target_chars = max(1, target_tokens * CHARS_PER_TOKEN)
    overlap_chars = max(0, overlap_tokens * CHARS_PER_TOKEN)
    if overlap_chars >= target_chars:
        overlap_chars = max(0, target_chars // 4)

    if len(normalized) <= target_chars:
        return [normalized]

    segments = _split_prose_and_tables(normalized)
    if not segments:
        return []

    # No table structure detected → classic sliding window on whole text.
    if all(kind == "prose" for kind, _ in segments):
        return _sliding_window(
            normalized,
            target_chars=target_chars,
            overlap_chars=overlap_chars,
        )

    chunks: list[str] = []
    for kind, segment in segments:
        if kind == "table":
            chunks.extend(_chunk_table(segment, target_chars=target_chars))
        else:
            chunks.extend(
                _sliding_window(
                    segment,
                    target_chars=target_chars,
                    overlap_chars=overlap_chars,
                )
            )
    return chunks
