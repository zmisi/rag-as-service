"""H1–H6 section tree builder (F04).

Industry-aligned extras:
- Numbered outline normalization (``2.1.1`` → parent ``2.1`` + leaf)
- Chinese chapter titles (``第…章``) promoted to H1; cover synthetic ``# N``
- HTML / Markdown escape sanitization before persist
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_NUMBERED_TITLE_RE = re.compile(r"^(\d+(?:\.\d+)*)(?:\s+(.*))?$")
_MD_ESC_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|>])")
# 第二章 / 第2章 / 第十章 / 第十一章 …
_CHAPTER_TITLE_RE = re.compile(
    r"^第([一二三四五六七八九十百千零〇两\d]+)章(?:\s*(.*))?$"
)
_CN_DIGIT = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}

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


def _parse_cn_int(token: str) -> int | None:
    """Parse a short Chinese / Arabic numeral used in 第N章 (1–99)."""
    s = (token or "").strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if s.startswith("十"):
        ones = _CN_DIGIT.get(s[1:])
        return 10 + ones if ones is not None else None
    if "十" in s:
        left, _, right = s.partition("十")
        tens = _CN_DIGIT.get(left)
        if tens is None:
            return None
        if not right:
            return tens * 10
        ones = _CN_DIGIT.get(right)
        return tens * 10 + ones if ones is not None else None
    return _CN_DIGIT.get(s)


def chinese_chapter_number(title: str) -> int | None:
    """Return N if title is ``第N章…`` (Chinese or Arabic N); else None."""
    m = _CHAPTER_TITLE_RE.match((title or "").strip())
    if not m:
        return None
    return _parse_cn_int(m.group(1))


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

    ``第…章`` titles are always emitted as H1 (Docling often flattens to ``##``)
    and cover synthetic chapter number ``N`` (F04-T24).
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
        # Still promote 第N章 → H1 when present without numbered leaves.
        out_plain: list[str] = []
        changed = False
        for raw in lines:
            stripped = raw.strip()
            m = _HEADING_RE.match(stripped)
            if not m:
                out_plain.append(raw)
                continue
            title = m.group(2).strip()
            if chinese_chapter_number(title) is not None:
                out_plain.append(f"# {sanitize_index_text(title)}")
                changed = True
            else:
                out_plain.append(raw)
        return "\n".join(out_plain) if changed else markdown

    out: list[str] = []
    emitted: set[str] = set()
    # Simulated heading stack: (level, is_numbered_title, title)
    stack: list[tuple[int, bool, str]] = []

    def close_to(level: int) -> None:
        while stack and stack[-1][0] >= level:
            stack.pop()

    def covered_by_named_ancestor(prefix: str, syn_level: int) -> bool:
        """Skip synthetic parent when a real named ancestor already covers it."""
        if any(not is_num and lvl <= syn_level for lvl, is_num, _t in stack):
            return True
        # 第N章 covers synthetic chapter number N (even if hash level was wrong
        # before promotion — stack titles are already promoted to H1).
        first = prefix.split(".", 1)[0]
        if first.isdigit():
            n = int(first)
            for _lvl, is_num, title in stack:
                if not is_num and chinese_chapter_number(title) == n:
                    return True
        return False

    for raw in lines:
        stripped = raw.strip()
        m = _HEADING_RE.match(stripped)
        if not m:
            out.append(raw)
            continue

        title = m.group(2).strip()
        parsed = _numbered_parts(title)
        if not parsed:
            if chinese_chapter_number(title) is not None:
                level = 1
            else:
                level = min(max(len(m.group(1)), 1), MAX_SECTION_LEVEL)
            clean = sanitize_index_text(title)
            close_to(level)
            out.append(f"{'#' * level} {clean}")
            stack.append((level, False, clean))
            continue

        num_str, parts, rest = parsed
        # Emit missing ancestors as synthetic headings (depth 1 .. n-1).
        for depth in range(1, len(parts)):
            prefix = ".".join(parts[:depth])
            if prefix in emitted:
                continue
            level = min(depth, MAX_SECTION_LEVEL)
            if covered_by_named_ancestor(prefix, level):
                # Real named ancestor already covers this level.
                emitted.add(prefix)
                continue
            close_to(level)
            out.append(f"{'#' * level} {prefix}")
            emitted.add(prefix)
            stack.append((level, True, prefix))

        level = min(len(parts), MAX_SECTION_LEVEL)
        display = f"{num_str} {rest}".strip() if rest else num_str
        clean_display = sanitize_index_text(display)
        close_to(level)
        out.append(f"{'#' * level} {clean_display}")
        emitted.add(num_str)
        stack.append((level, True, clean_display))

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
