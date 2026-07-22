"""Text chunking with fixed token budget (char approximation)."""

from __future__ import annotations

from rag_api.indexing.constants import (
    CHARS_PER_TOKEN,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_TARGET_TOKENS,
)


def chunk_text(
    text: str,
    *,
    target_tokens: int = CHUNK_TARGET_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> list[str]:
    """Split text into overlapping chunks. Empty / whitespace → []."""
    normalized = (text or "").strip()
    if not normalized:
        return []

    target_chars = max(1, target_tokens * CHARS_PER_TOKEN)
    overlap_chars = max(0, overlap_tokens * CHARS_PER_TOKEN)
    if overlap_chars >= target_chars:
        overlap_chars = max(0, target_chars // 4)

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
