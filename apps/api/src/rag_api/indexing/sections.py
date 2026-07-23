"""H1/H2 section tree builder (F04)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass(frozen=True)
class SectionDraft:
    """In-memory leaf section before DB persist."""

    level: int  # 1 or 2
    title: str
    path: str
    content: str
    h1_title: str | None = None  # for H2 parent linking


def build_section_tree(
    markdown: str,
    *,
    title_fallback: str = "文档",
) -> list[SectionDraft]:
    """Build Phase-1 H1/H2 leaf sections from Markdown.

    - H3+ body merges into the nearest H2 (or H1 if no H2 yet).
    - No headings → single section with ``title_fallback``.
    - Non-empty H1 intro before first H2 becomes its own level-1 leaf.
    """
    text = (markdown or "").strip()
    if not text:
        return []

    fallback = (title_fallback or "文档").strip() or "文档"
    lines = text.splitlines()

    # Scan for any AT1–H6 heading
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
                    content=body,
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
                content=body,
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
                    content=body,
                    h1_title=None,
                )
            )

    for raw in lines:
        m = _HEADING_RE.match(raw.strip())
        if m:
            level = len(m.group(1))
            title = m.group(2).strip() or fallback
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
                    content=body,
                    h1_title=None,
                )
            )

    return [d for d in drafts if d.content.strip()]
