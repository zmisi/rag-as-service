"""H1/H2 section tree builder (F04).

Industry-aligned extras:
- Numbered outline normalization (``2.1.1`` → parent ``2.1`` + leaf)
- HTML / Markdown escape sanitization before persist
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_NUMBERED_TITLE_RE = re.compile(r"^(\d+(?:\.\d+)*)(?:\s+(.*))?$")
_MD_ESC_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|>])")


@dataclass(frozen=True)
class SectionDraft:
    """In-memory leaf section before DB persist."""

    level: int  # 1 or 2
    title: str
    path: str
    content: str
    h1_title: str | None = None  # for H2 parent linking


def sanitize_index_text(text: str) -> str:
    """Unescape HTML entities and common Markdown backslash escapes."""
    if not text:
        return ""
    out = html.unescape(text)
    out = _MD_ESC_RE.sub(r"\1", out)
    return out


def _numbered_parts(title: str) -> tuple[str, list[str], str] | None:
    """Return (num_str, parts, rest) if title starts with a dotted outline number."""
    m = _NUMBERED_TITLE_RE.match(title.strip())
    if not m:
        return None
    num_str = m.group(1)
    rest = (m.group(2) or "").strip()
    return num_str, num_str.split("."), rest


def _md_heading_level(depth: int, *, h1_depth: int, h2_depth: int) -> int:
    if depth <= h1_depth:
        return 1
    if depth <= h2_depth:
        return 2
    return 3


def normalize_numbered_outline(markdown: str) -> str:
    """Rewrite numbered headings into a proper H1/H2/H3+ outline.

    When a doc only has deep leaves like ``## 2.1.1 …`` / ``## 2.2.1 …``,
    insert synthetic parents (``# 2.1``, ``# 2.2``) and remap levels so
    ``build_section_tree`` yields paths such as ``2.1 > 2.1.1 …``.
    """
    lines = (markdown or "").splitlines()
    numbered_depths: list[int] = []
    for raw in lines:
        m = _HEADING_RE.match(raw.strip())
        if not m:
            continue
        parsed = _numbered_parts(m.group(2).strip())
        if parsed:
            numbered_depths.append(len(parsed[1]))

    if not numbered_depths:
        return markdown

    max_depth = max(numbered_depths)
    min_depth = min(numbered_depths)
    # Prefer keeping deepest numbered titles as H2 leaves when they are 3+.
    if max_depth >= 3 and min_depth >= 2:
        h1_depth = max_depth - 1
        h2_depth = max_depth
    else:
        h1_depth = 1
        h2_depth = 2

    out: list[str] = []
    emitted: set[str] = set()

    for raw in lines:
        stripped = raw.strip()
        m = _HEADING_RE.match(stripped)
        if not m:
            out.append(raw)
            continue

        title = m.group(2).strip()
        parsed = _numbered_parts(title)
        if not parsed:
            # Non-numbered: keep relative hash count (capped 1..6), sanitize title.
            level = min(max(len(m.group(1)), 1), 6)
            out.append(f"{'#' * level} {sanitize_index_text(title)}")
            continue

        num_str, parts, rest = parsed
        # Emit missing ancestors as synthetic headings.
        for depth in range(1, len(parts)):
            prefix = ".".join(parts[:depth])
            if prefix in emitted:
                continue
            level = _md_heading_level(depth, h1_depth=h1_depth, h2_depth=h2_depth)
            out.append(f"{'#' * level} {prefix}")
            emitted.add(prefix)

        level = _md_heading_level(
            len(parts), h1_depth=h1_depth, h2_depth=h2_depth
        )
        display = f"{num_str} {rest}".strip() if rest else num_str
        out.append(f"{'#' * level} {sanitize_index_text(display)}")
        emitted.add(num_str)

    return "\n".join(out)


def build_section_tree(
    markdown: str,
    *,
    title_fallback: str = "文档",
) -> list[SectionDraft]:
    """Build Phase-1 H1/H2 leaf sections from Markdown.

    - H3+ body merges into the nearest H2 (or H1 if no H2 yet).
    - No headings → single section with ``title_fallback``.
    - Non-empty H1 intro before first H2 becomes its own level-1 leaf.
    - Numbered outlines are normalized; content is sanitized.
    """
    text = sanitize_index_text((markdown or "").strip())
    if not text:
        return []

    text = normalize_numbered_outline(text).strip()
    if not text:
        return []

    fallback = sanitize_index_text((title_fallback or "文档").strip()) or "文档"
    lines = text.splitlines()

    # Scan for any H1–H6 heading
    has_heading = any(_HEADING_RE.match(ln.strip()) for ln in lines)
    if not has_heading:
        return [
            SectionDraft(
                level=1,
                title=fallback,
                path=fallback,
                content=text,
                h1_title=None,
            )
        ]

    drafts: list[SectionDraft] = []
    current_h1: str | None = None
    # Buffer for H1 intro (before first H2 under this H1)
    intro: list[str] = []
    # Current H2 leaf body
    h2_title: str | None = None
    h2_body: list[str] = []
    # H1-only body when never saw H2
    h1_only_body: list[str] = []
    mode = "before"  # before | intro | h2 | h1_only

    def flush_intro() -> None:
        nonlocal intro
        body = "\n".join(intro).strip()
        intro = []
        if body and current_h1:
            drafts.append(
                SectionDraft(
                    level=1,
                    title=current_h1,
                    path=current_h1,
                    content=sanitize_index_text(body),
                    h1_title=None,
                )
            )

    def flush_h2() -> None:
        nonlocal h2_title, h2_body
        if h2_title is None:
            return
        body = "\n".join(h2_body).strip()
        h2_body = []
        title = h2_title
        h2_title = None
        if not body:
            return
        path = f"{current_h1} > {title}" if current_h1 else title
        drafts.append(
            SectionDraft(
                level=2,
                title=title,
                path=path,
                content=sanitize_index_text(body),
                h1_title=current_h1,
            )
        )

    def flush_h1_only() -> None:
        nonlocal h1_only_body
        body = "\n".join(h1_only_body).strip()
        h1_only_body = []
        if body and current_h1:
            drafts.append(
                SectionDraft(
                    level=1,
                    title=current_h1,
                    path=current_h1,
                    content=sanitize_index_text(body),
                    h1_title=None,
                )
            )

    for raw in lines:
        m = _HEADING_RE.match(raw.strip())
        if m:
            level = len(m.group(1))
            title = sanitize_index_text(m.group(2).strip()) or fallback
            if level == 1:
                flush_h2()
                flush_intro()
                flush_h1_only()
                current_h1 = title
                mode = "intro"
                intro = []
                h1_only_body = []
            elif level == 2:
                if mode == "intro":
                    flush_intro()
                elif mode == "h2":
                    flush_h2()
                elif mode == "h1_only":
                    # Unexpected H2 after treating as h1_only — flush
                    flush_h1_only()
                mode = "h2"
                h2_title = title
                h2_body = []
            else:
                # H3+: part of current body
                if mode == "h2":
                    h2_body.append(raw)
                elif mode == "intro":
                    intro.append(raw)
                elif mode == "h1_only":
                    h1_only_body.append(raw)
                else:
                    # orphan deep heading before any H1/H2 → synthetic H2
                    mode = "h2"
                    h2_title = title
                    h2_body = []
            continue

        if mode == "intro":
            intro.append(raw)
        elif mode == "h2":
            h2_body.append(raw)
        elif mode == "h1_only":
            h1_only_body.append(raw)
        elif mode == "before":
            # preamble before first heading
            if current_h1 is None:
                # Keep preamble until first heading; stash as pending intro of synthetic
                intro.append(raw)
        else:
            intro.append(raw)

    # End of document
    if mode == "intro":
        # H1 with no H2 → entire intro is H1 leaf
        h1_only_body = intro
        intro = []
        flush_h1_only()
    elif mode == "h2":
        flush_h2()
    elif mode == "h1_only":
        flush_h1_only()
    elif mode == "before" and intro:
        # Only preamble with headings never matched — treat as single section
        body = "\n".join(intro).strip()
        if body:
            drafts.append(
                SectionDraft(
                    level=1,
                    title=fallback,
                    path=fallback,
                    content=sanitize_index_text(body),
                    h1_title=None,
                )
            )

    return [d for d in drafts if d.content.strip()]


def infer_chunk_type(content: str) -> str:
    """Classify leaf for ``chunk_type`` (text | table | mixed)."""
    body = content or ""
    has_table = bool(re.search(r"^\|.+\|\s*$", body, re.MULTILINE)) and (
        "---" in body or "|-" in body
    )
    has_text = bool(re.sub(r"^\|.*\|\s*$", "", body, flags=re.MULTILINE).strip())
    if has_table and has_text:
        return "mixed"
    if has_table:
        return "table"
    return "text"
