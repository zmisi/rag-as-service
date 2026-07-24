"""Unit tests for F04 PDF skeleton-aware routing + ParseBlocks."""

from __future__ import annotations

import io
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from rag_api.indexing.parse import (
    ParseError,
    PdfFastMetrics,
    RoutedDocumentParser,
    ScriptedDocumentParser,
    extract_pdf_pages_pymupdf,
    pdf_fast_quality_ok,
)
from rag_api.indexing.parse_blocks import (
    ParseBlock,
    blocks_to_markdown,
    count_block_kinds,
    markdown_to_blocks,
)
from rag_api.indexing.pdf_skeleton import detect_pdf_skeleton
from rag_api.indexing.sections import build_section_tree


def _make_text_pdf(text: str, *, pages: int = 1) -> bytes:
    import fitz

    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        body = text if pages == 1 else f"{text}\npage-{i + 1}"
        page.insert_textbox(fitz.Rect(36, 36, 560, 800), body, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def _make_toc_pdf() -> bytes:
    """PDF with outline/bookmarks (skeleton via TOC)."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(
        fitz.Rect(36, 36, 560, 800),
        "Chapter One body UNIQUE_SKELETON_TOC\n\nmore text " * 10,
        fontsize=11,
    )
    page2 = doc.new_page()
    page2.insert_textbox(
        fitz.Rect(36, 36, 560, 800),
        "Chapter Two body\n\n" + ("x " * 40),
        fontsize=11,
    )
    # TOC entries: [level, title, page]
    doc.set_toc(
        [
            [1, "Chapter One", 1],
            [2, "Section A", 1],
            [1, "Chapter Two", 2],
        ]
    )
    data = doc.tobytes()
    doc.close()
    return data


@dataclass
class _TrackingDocling:
    calls: list[str]
    result: str = "# From Docling\n\nbody"

    def parse_to_markdown(self, filename: str, data: bytes) -> str:
        self.calls.append(filename)
        return self.result


def _settings(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = dict(
        pdf_fast_min_chars=80,
        pdf_fast_min_chars_per_page=40.0,
        pdf_fast_min_printable_ratio=0.85,
        pdf_fast_max_empty_page_ratio=0.50,
        pdf_skeleton_min_toc=1,
        pdf_skeleton_min_heading_candidates=3,
        pdf_force_structure=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_pdf_fast_quality_ok_and_fail() -> None:
    good = PdfFastMetrics(
        page_count=2,
        total_chars=200,
        chars_per_page=100.0,
        printable_ratio=0.95,
        empty_page_ratio=0.0,
        page_texts=("a" * 100, "b" * 100),
    )
    assert pdf_fast_quality_ok(
        good,
        min_chars=80,
        min_chars_per_page=40.0,
        min_printable_ratio=0.85,
        max_empty_page_ratio=0.50,
    )
    bad = PdfFastMetrics(
        page_count=2,
        total_chars=90,
        chars_per_page=45.0,
        printable_ratio=0.50,
        empty_page_ratio=0.0,
        page_texts=("x", "y"),
    )
    assert not pdf_fast_quality_ok(
        bad,
        min_chars=80,
        min_chars_per_page=40.0,
        min_printable_ratio=0.85,
        max_empty_page_ratio=0.50,
    )


def test_f04_t13_plain_pdf_uses_pymupdf() -> None:
    """F04-T13: no-skeleton text PDF stays on PyMuPDF."""
    phrase = "UNIQUE_PHRASE_PYMUPDF_FASTPATH_XYZ "
    text = (phrase * 8).strip()
    assert len("".join(ch for ch in text if not ch.isspace())) >= 80
    pdf = _make_text_pdf(text)
    tracker = _TrackingDocling(calls=[])
    parser = RoutedDocumentParser(docling=tracker, settings=_settings())
    outcome = parser.parse_outcome("guide.pdf", pdf)
    assert outcome.route == "pymupdf"
    assert outcome.skeleton is False
    assert "UNIQUE_PHRASE_PYMUPDF_FASTPATH_XYZ" in outcome.text
    assert tracker.calls == []
    assert parser.last_routes == [("guide.pdf", "pymupdf")]


def test_f04_t14_quality_fail_falls_back_to_docling() -> None:
    """F04-T14: no-skeleton + strict quality gate → Docling."""
    pdf = _make_text_pdf("short but printable text hello world " * 5)
    tracker = _TrackingDocling(
        calls=[],
        result="# Docling\n\nfallback body UNIQUE_DOC_FALLBACK",
    )
    parser = RoutedDocumentParser(
        docling=tracker,
        settings=_settings(
            pdf_fast_min_chars=10_000,
            pdf_fast_min_chars_per_page=5_000.0,
        ),
    )
    outcome = parser.parse_outcome("weak.pdf", pdf)
    assert outcome.route == "docling"
    assert "UNIQUE_DOC_FALLBACK" in outcome.text
    assert tracker.calls == ["weak.pdf"]


def test_f04_t14_pymupdf_error_falls_back_to_docling(monkeypatch) -> None:
    tracker = _TrackingDocling(calls=[], result="recovered")
    parser = RoutedDocumentParser(docling=tracker, settings=_settings())

    def _boom(_data: bytes) -> PdfFastMetrics:
        raise ParseError("pymupdf explode")

    monkeypatch.setattr(
        "rag_api.indexing.parse.extract_pdf_pages_pymupdf",
        _boom,
    )
    outcome = parser.parse_outcome("broken.pdf", b"%PDF-1.4 stub")
    assert outcome.route == "docling"
    assert outcome.text == "recovered"
    assert tracker.calls == ["broken.pdf"]


def test_empty_text_layer_pdf_stays_pymupdf_no_docling() -> None:
    import fitz

    doc = fitz.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    tracker = _TrackingDocling(calls=[])
    parser = RoutedDocumentParser(docling=tracker, settings=_settings())
    outcome = parser.parse_outcome("scan.pdf", data)
    assert outcome.route == "pymupdf"
    assert outcome.text == ""
    assert tracker.calls == []


def test_f04_t15_office_uses_lightweight_not_docling() -> None:
    """F08: .docx uses python-docx route, not Docling/PyMuPDF."""
    from docx import Document

    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("Office lite body")
    doc.save(buf)
    data = buf.getvalue()

    tracker = _TrackingDocling(calls=[])
    parser = RoutedDocumentParser(docling=tracker, settings=_settings())
    outcome = parser.parse_outcome("manual.docx", data)
    assert outcome.route == "docx"
    assert "Office lite body" in outcome.text
    assert tracker.calls == []


def test_extract_pdf_pages_metrics() -> None:
    pdf = _make_text_pdf("Hello 世界 " * 20, pages=2)
    metrics = extract_pdf_pages_pymupdf(pdf)
    assert metrics.page_count == 2
    assert metrics.total_chars >= 80
    assert metrics.printable_ratio >= 0.85


def test_quality_fail_docling_error_raises() -> None:
    pdf = _make_text_pdf("hello " * 20)

    class Boom:
        def parse_to_markdown(self, filename: str, data: bytes) -> str:
            raise ParseError("docling boom")

    parser = RoutedDocumentParser(
        docling=Boom(),
        settings=_settings(pdf_fast_min_chars=10_000),
    )
    with pytest.raises(ParseError, match="docling boom"):
        parser.parse_outcome("x.pdf", pdf)


def test_scripted_parser_still_works() -> None:
    p = ScriptedDocumentParser(mapping={"a.txt": "AAA"}, route="text")
    assert p.parse_outcome("a.txt", b"").route == "text"


def test_detect_skeleton_toc() -> None:
    pdf = _make_toc_pdf()
    probe = detect_pdf_skeleton(pdf, min_toc=1, min_heading_candidates=99)
    assert probe.has_skeleton is True
    assert probe.reason == "toc"
    assert probe.toc_entries >= 1


def test_detect_skeleton_force() -> None:
    pdf = _make_text_pdf("plain " * 40)
    probe = detect_pdf_skeleton(pdf, force=True)
    assert probe.has_skeleton is True
    assert probe.reason == "force"


def test_detect_skeleton_plain_none() -> None:
    pdf = _make_text_pdf("plain uniform body " * 40)
    probe = detect_pdf_skeleton(
        pdf,
        min_toc=1,
        min_heading_candidates=99,
    )
    assert probe.has_skeleton is False
    assert probe.reason == "none"


def test_f04_t16_skeleton_pdf_uses_docling() -> None:
    """F04-T16: TOC skeleton → Docling structure path with heading tags."""
    pdf = _make_toc_pdf()
    tracker = _TrackingDocling(
        calls=[],
        result=(
            "# Chapter One\n\n"
            "## Section A\n\n"
            "body UNIQUE_SKELETON_TOC\n\n"
            "### Deep H3\n\n"
            "nested\n\n"
            "| a | b |\n| --- | --- |\n| 1 | 2 |\n\n"
            "![chart](img.png)\n"
        ),
    )
    parser = RoutedDocumentParser(docling=tracker, settings=_settings())
    outcome = parser.parse_outcome("book.pdf", pdf)
    assert outcome.route == "docling"
    assert outcome.skeleton is True
    assert tracker.calls == ["book.pdf"]
    assert outcome.block_counts is not None
    assert outcome.block_counts["heading"] >= 2
    assert outcome.block_counts["table"] >= 1
    assert outcome.block_counts["image"] >= 1
    assert "# Chapter One" in outcome.text
    assert "[图片" in outcome.text


def test_f04_t17_skeleton_without_docling_fails() -> None:
    """F04-T17: skeleton PDF must not silently flatten when Docling missing."""
    pdf = _make_toc_pdf()

    class Missing:
        def parse_to_markdown(self, filename: str, data: bytes) -> str:
            raise ParseError("docling is not installed; pip install 'rag-api[docling]'")

    parser = RoutedDocumentParser(docling=Missing(), settings=_settings())
    with pytest.raises(ParseError, match="docling"):
        parser.parse_outcome("book.pdf", pdf)


def test_force_structure_uses_docling() -> None:
    pdf = _make_text_pdf("plain " * 40)
    tracker = _TrackingDocling(calls=[], result="# Forced\n\nbody")
    parser = RoutedDocumentParser(
        docling=tracker,
        settings=_settings(pdf_force_structure=True),
    )
    outcome = parser.parse_outcome("forced.pdf", pdf)
    assert outcome.route == "docling"
    assert outcome.skeleton is True
    assert tracker.calls == ["forced.pdf"]


def test_parse_blocks_roundtrip_and_section_tree() -> None:
    md = (
        "# H1 Title\n\n"
        "intro\n\n"
        "## H2 A\n\n"
        "body-a UNIQUE_A\n\n"
        "### H3 deep\n\n"
        "deep-body\n\n"
        "## H2 B\n\n"
        "body-b UNIQUE_B\n"
    )
    blocks = markdown_to_blocks(md)
    assert count_block_kinds(blocks)["heading"] == 4
    out = blocks_to_markdown(blocks)
    drafts = build_section_tree(out, title_fallback="doc")
    paths = {d.path for d in drafts}
    assert any("H2 A" in p for p in paths)
    assert any("H2 B" in p for p in paths)
    # H3 merged into H2 A content
    h2a = next(d for d in drafts if "H2 A" in d.path)
    assert "deep-body" in h2a.content
    assert "UNIQUE_A" in h2a.content


def test_blocks_to_markdown_image_placeholder() -> None:
    blocks = [
        ParseBlock(kind="heading", level=1, text="Title"),
        ParseBlock(kind="image", caption="图1"),
        ParseBlock(kind="paragraph", text="after"),
    ]
    md = blocks_to_markdown(blocks)
    assert "[图片: 图1]" in md
    assert md.startswith("# Title")
