"""PDF skeleton detection (TOC + font-size heading candidates)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkeletonProbe:
    has_skeleton: bool
    reason: str  # toc | font | force | none | empty
    toc_entries: int = 0
    heading_candidates: int = 0


def detect_pdf_skeleton(
    data: bytes,
    *,
    min_toc: int = 1,
    min_heading_candidates: int = 3,
    force: bool = False,
    heading_size_ratio: float = 1.25,
    max_heading_chars: int = 80,
    sample_pages: int = 8,
) -> SkeletonProbe:
    """Lightweight PyMuPDF probe. Does not write to DB.

    Raises ``RuntimeError`` if PyMuPDF is missing or the PDF cannot be opened.
    """
    if force:
        return SkeletonProbe(has_skeleton=True, reason="force")

    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError(
            "pymupdf is not installed; pip install pymupdf"
        ) from exc

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"PyMuPDF failed to open PDF: {exc}") from exc

    try:
        toc = doc.get_toc() or []
        toc_n = len(toc)
        if toc_n >= min_toc:
            return SkeletonProbe(
                has_skeleton=True,
                reason="toc",
                toc_entries=toc_n,
            )

        sizes: list[float] = []
        page_count = doc.page_count
        if page_count <= 0:
            return SkeletonProbe(has_skeleton=False, reason="none")

        if page_count <= sample_pages:
            indices = list(range(page_count))
        else:
            start = max(0, (page_count - sample_pages) // 2)
            indices = list(range(start, start + sample_pages))

        for i in indices:
            page = doc.load_page(i)
            try:
                blocks = page.get_text("dict").get("blocks") or []
            except Exception:  # noqa: BLE001
                continue
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines") or []:
                    spans = line.get("spans") or []
                    if not spans:
                        continue
                    text = "".join(str(s.get("text") or "") for s in spans).strip()
                    if not text:
                        continue
                    size = max(float(s.get("size") or 0.0) for s in spans)
                    if size > 0:
                        sizes.append(size)

        if not sizes:
            return SkeletonProbe(
                has_skeleton=False,
                reason="none",
                toc_entries=toc_n,
            )

        sizes_sorted = sorted(sizes)
        body = sizes_sorted[len(sizes_sorted) // 2]
        threshold = body * heading_size_ratio
        candidates = 0

        for i in indices:
            page = doc.load_page(i)
            try:
                blocks = page.get_text("dict").get("blocks") or []
            except Exception:  # noqa: BLE001
                continue
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines") or []:
                    spans = line.get("spans") or []
                    if not spans:
                        continue
                    text = "".join(str(s.get("text") or "") for s in spans).strip()
                    size = max(float(s.get("size") or 0.0) for s in spans)
                    if (
                        text
                        and len(text) <= max_heading_chars
                        and size >= threshold
                        and size > body
                    ):
                        candidates += 1

        if candidates >= min_heading_candidates:
            return SkeletonProbe(
                has_skeleton=True,
                reason="font",
                toc_entries=toc_n,
                heading_candidates=candidates,
            )
        return SkeletonProbe(
            has_skeleton=False,
            reason="none",
            toc_entries=toc_n,
            heading_candidates=candidates,
        )
    finally:
        doc.close()
