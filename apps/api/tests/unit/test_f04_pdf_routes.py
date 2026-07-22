"""Unit tests for F04 PDF dual-route parsing (PyMuPDF → Docling)."""

from __future__ import annotations

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


def _make_text_pdf(text: str, *, pages: int = 1) -> bytes:
    import fitz

    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        body = text if pages == 1 else f"{text}\npage-{i + 1}"
        # textbox wraps so long strings are not truncated by single insert_text.
        page.insert_textbox(fitz.Rect(36, 36, 560, 800), body, fontsize=11)
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


def test_f04_t13_text_layer_pdf_uses_pymupdf() -> None:
    """F04-T13: extractable text PDF stays on PyMuPDF; Docling not called."""
    phrase = "UNIQUE_PHRASE_PYMUPDF_FASTPATH_XYZ "
    text = (phrase * 8).strip()
    assert len("".join(ch for ch in text if not ch.isspace())) >= 80
    pdf = _make_text_pdf(text)
    tracker = _TrackingDocling(calls=[])
    parser = RoutedDocumentParser(docling=tracker, settings=_settings())
    outcome = parser.parse_outcome("guide.pdf", pdf)
    assert outcome.route == "pymupdf"
    assert "UNIQUE_PHRASE_PYMUPDF_FASTPATH_XYZ" in outcome.text
    assert tracker.calls == []
    assert parser.last_routes == [("guide.pdf", "pymupdf")]


def test_f04_t14_quality_fail_falls_back_to_docling() -> None:
    """F04-T14: low quality / strict gate → Docling."""
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


def test_f04_t14_pymupdf_error_falls_back_to_docling() -> None:
    tracker = _TrackingDocling(calls=[], result="recovered")
    parser = RoutedDocumentParser(docling=tracker, settings=_settings())
    outcome = parser.parse_outcome("broken.pdf", b"not-a-pdf")
    assert outcome.route == "docling"
    assert outcome.text == "recovered"
    assert tracker.calls == ["broken.pdf"]


def test_empty_text_layer_pdf_stays_pymupdf_no_docling() -> None:
    """Textless PDF: empty success path; do not call Docling for OCR."""
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


def test_f04_t15_docx_bypasses_pymupdf() -> None:
    """F04-T15: Office goes Docling directly."""
    tracker = _TrackingDocling(calls=[], result="# Office\n\nfrom docling")
    parser = RoutedDocumentParser(docling=tracker, settings=_settings())
    outcome = parser.parse_outcome("manual.docx", b"PK\x03\x04-fake-docx")
    assert outcome.route == "docling"
    assert "from docling" in outcome.text
    assert tracker.calls == ["manual.docx"]


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
