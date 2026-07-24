"""H1–H6 section tree builder (F04).

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

MAX_SECTION_LEVEL = 6


@dataclass(frozen=True)
class SectionDraft:
    """In-memory leaf section before DB persist."""

    level: int  # 1..6
    title: str
    path: str
    content: str
    parent_path: str | None = None  # path of parent section, if any


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


def normalize_numbered_outline(markdown: str) -> str:
    """Rewrite numbered headings into an H1–H6 outline.

    When a doc only has deep leaves like ``## 2.1.1 …`` / ``## 2.2.1 …``,
    insert synthetic parents and map numbering depth to Markdown levels
    ``min(depth, 6)`` so ``build_section_tree`` yields paths such as
    ``2 > 2.1 > 2.1.1 …``.

    If a non-numbered heading is already open (e.g. ``# 第二章 …``), do **not**
    insert a same-or-shallower pure-number synthetic parent (``# 2``); leaf paths
    keep the real ancestor title (F04-T22).
    """
    lines = (markdown or "").splitlines()
    has_numbered = False
    for raw in lines:
        m = _HEADING_RE.match(raw.strip())
        if not m:
            continue
        if _numbered_parts(m.group(2).strip()):
            has_numbered = True
            break

    if not has_numbered:
        return markdown

    out: list[str] = []
    emitted: set[str] = set()
    # Simulated heading stack: (level, is_numbered_title)
    stack: list[tuple[int, bool]] = []

    def close_to(level: int) -> None:
        while stack and stack[-1][0] >= level:
            stack.pop()

    def covered_by_non_numbered(syn_level: int) -> bool:
        return any(not is_num and lvl <= syn_level for lvl, is_num in stack)

    for raw in lines:
        stripped = raw.strip()
        m = _HEADING_RE.match(stripped)
        if not m:
            out.append(raw)
            continue

        title = m.group(2).strip()
        parsed = _numbered_parts(title)
        if not parsed:
            level = min(max(len(m.group(1)), 1), MAX_SECTION_LEVEL)
            close_to(level)
            out.append(f"{'#' * level} {sanitize_index_text(title)}")
            stack.append((level, False))
            continue

        num_str, parts, rest = parsed
        # Emit missing ancestors as synthetic headings (depth 1 .. n-1).
        for depth in range(1, len(parts)):
            prefix = ".".join(parts[:depth])
            if prefix in emitted:
                continue
            level = min(depth, MAX_SECTION_LEVEL)
            if covered_by_non_numbered(level):
                # Real non-numbered ancestor already covers this level.
                emitted.add(prefix)
                continue
            close_to(level)
            out.append(f"{'#' * level} {prefix}")
            emitted.add(prefix)
            stack.append((level, True))

        level = min(len(parts), MAX_SECTION_LEVEL)
        display = f"{num_str} {rest}".strip() if rest else num_str
        close_to(level)
        out.append(f"{'#' * level} {sanitize_index_text(display)}")
        emitted.add(num_str)
        stack.append((level, True))

    return "\n".join(out)


def _path_of(titles: list[str]) -> str:
    return " > ".join(titles)


@dataclass
class _StackFrame:
    level: int
    title: str
    body: list[str]


def build_section_tree(
    markdown: str,
    *,
    title_fallback: str = "文档",
) -> list[SectionDraft]:
    """Build H1–H6 leaf sections from Markdown.

    - Heading stack: body belongs to the deepest open heading.
    - Same-or-shallower heading flushes deeper open sections first.
    - Hashes beyond 6 are not matched by Markdown; body stays under H6.
    - No headings → single section with ``title_fallback``.
    - Empty bodies are discarded.
    - Drafts are emitted shallow-first so parents precede children for persist.
    """
    text = sanitize_index_text((markdown or "").strip())
    if not text:
        return []

    text = normalize_numbered_outline(text).strip()
    if not text:
        return []

    fallback = sanitize_index_text((title_fallback or "文档").strip()) or "文档"
    lines = text.splitlines()

    has_heading = any(_HEADING_RE.match(ln.strip()) for ln in lines)
    if not has_heading:
        return [
            SectionDraft(
                level=1,
                title=fallback,
                path=fallback,
                content=text,
                parent_path=None,
            )
        ]

    drafts: list[SectionDraft] = []
    stack: list[_StackFrame] = []
    preamble: list[str] = []

    def titles() -> list[str]:
        return [f.title for f in stack]

    def make_draft(frame: _StackFrame) -> SectionDraft | None:
        body = "\n".join(frame.body).strip()
        if not body:
            return None
        tlist = titles() + [frame.title]
        path = _path_of(tlist)
        parent_path = _path_of(tlist[:-1]) if len(tlist) > 1 else None
        return SectionDraft(
            level=frame.level,
            title=frame.title,
            path=path,
            content=sanitize_index_text(body),
            parent_path=parent_path,
        )

    def flush_deeper_or_equal(level: int) -> None:
        """Close open frames with level >= ``level``; emit shallow-first."""
        closed: list[SectionDraft] = []
        while stack and stack[-1].level >= level:
            frame = stack.pop()
            draft = make_draft(frame)
            if draft is not None:
                closed.append(draft)
        drafts.extend(reversed(closed))

    for raw in lines:
        m = _HEADING_RE.match(raw.strip())
        if m:
            level = min(len(m.group(1)), MAX_SECTION_LEVEL)
            title = sanitize_index_text(m.group(2).strip()) or fallback

            flush_deeper_or_equal(level)

            frame = _StackFrame(level=level, title=title, body=[])
            if preamble and not stack:
                frame.body.extend(preamble)
                preamble = []
            stack.append(frame)
            continue

        if not stack:
            preamble.append(raw)
        else:
            stack[-1].body.append(raw)

    # EOF: flush entire stack shallow-first.
    closed: list[SectionDraft] = []
    while stack:
        frame = stack.pop()
        draft = make_draft(frame)
        if draft is not None:
            closed.append(draft)
    drafts.extend(reversed(closed))

    if not drafts and preamble:
        body = "\n".join(preamble).strip()
        if body:
            drafts.append(
                SectionDraft(
                    level=1,
                    title=fallback,
                    path=fallback,
                    content=sanitize_index_text(body),
                    parent_path=None,
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
