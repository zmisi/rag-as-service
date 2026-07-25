"""Structured parse blocks (heading / paragraph / table / image) → Markdown."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]*)\)\s*$")
_TABLE_LINE_RE = re.compile(r"^\|.*\|$")


@dataclass(frozen=True)
class ParseBlock:
    """Tagged structural unit from the structure-aware parse path."""

    kind: str  # heading | paragraph | table | image
    text: str = ""
    level: int | None = None
    caption: str | None = None


def blocks_to_markdown(blocks: list[ParseBlock]) -> str:
    parts: list[str] = []
    for b in blocks:
        if b.kind == "heading":
            lvl = max(1, min(int(b.level or 1), 6))
            title = (b.text or "").strip()
            if title:
                parts.append(f"{'#' * lvl} {title}")
        elif b.kind == "paragraph":
            t = (b.text or "").strip()
            if t:
                parts.append(t)
        elif b.kind == "table":
            t = (b.text or "").strip()
            if t:
                parts.append(t)
        elif b.kind == "image":
            cap = (b.caption or b.text or "").strip()
            if cap:
                parts.append(f"[图片: {cap}]")
            else:
                parts.append("[图片]")
    return "\n\n".join(parts).strip()


def markdown_to_blocks(markdown: str) -> list[ParseBlock]:
    """Best-effort labeling of Markdown (e.g. Docling export) into ParseBlocks."""
    text = (markdown or "").strip()
    if not text:
        return []

    lines = text.splitlines()
    blocks: list[ParseBlock] = []
    i = 0
    para_buf: list[str] = []

    def flush_para() -> None:
        nonlocal para_buf
        body = "\n".join(para_buf).strip()
        para_buf = []
        if body:
            blocks.append(ParseBlock(kind="paragraph", text=body))

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped:
            flush_para()
            i += 1
            continue

        hm = _HEADING_RE.match(stripped)
        if hm:
            flush_para()
            blocks.append(
                ParseBlock(
                    kind="heading",
                    level=len(hm.group(1)),
                    text=hm.group(2).strip(),
                )
            )
            i += 1
            continue

        im = _IMAGE_RE.match(stripped)
        if im:
            flush_para()
            alt = (im.group(1) or "").strip()
            blocks.append(ParseBlock(kind="image", caption=alt or None, text=alt))
            i += 1
            continue

        if _TABLE_LINE_RE.match(stripped):
            flush_para()
            table_lines = [stripped]
            i += 1
            while i < len(lines) and _TABLE_LINE_RE.match(lines[i].strip()):
                table_lines.append(lines[i].strip())
                i += 1
            blocks.append(ParseBlock(kind="table", text="\n".join(table_lines)))
            continue

        para_buf.append(raw)
        i += 1

    flush_para()
    return blocks


def count_block_kinds(blocks: list[ParseBlock]) -> dict[str, int]:
    out = {"heading": 0, "paragraph": 0, "table": 0, "image": 0}
    for b in blocks:
        if b.kind in out:
            out[b.kind] += 1
    return out
