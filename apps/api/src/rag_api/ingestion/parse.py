"""Document parsing to Markdown (F04 / F08).

PDF routing: skeleton → Docling structure path; plain text → PyMuPDF;
quality gate is an auxiliary fallback on the no-skeleton path.
Office (.docx/.xlsx/.pptx): lightweight libraries (not Docling).
Text (.txt/.md): decode.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from rag_api.config import get_settings
from rag_api.indexing.parse_blocks import (
    ParseBlock,
    blocks_to_markdown,
    count_block_kinds,
    markdown_to_blocks,
)
from rag_api.indexing.pdf_skeleton import SkeletonProbe, detect_pdf_skeleton

logger = logging.getLogger(__name__)

_TEXT_SUFFIXES = frozenset({".txt", ".md", ".csv", ""})
_OFFICE_SUFFIXES = frozenset({".docx", ".pptx", ".xlsx"})
_LEGACY_OFFICE_SUFFIXES = frozenset({".doc", ".ppt", ".xls"})
_PDF_SUFFIX = ".pdf"
_FILE_SEPARATOR = "\n\n---\n\n"

# Letters / numbers / punctuation / symbols (Unicode categories) + CJK ranges.
_PRINTABLE_CATEGORIES = frozenset({"L", "N", "P", "S"})


def _is_quality_char(ch: str) -> bool:
    import unicodedata

    if unicodedata.category(ch)[0] in _PRINTABLE_CATEGORIES:
        return True
    o = ord(ch)
    return (
        0x3040 <= o <= 0x30FF  # kana
        or 0x3400 <= o <= 0x4DBF
        or 0x4E00 <= o <= 0x9FFF
        or 0xAC00 <= o <= 0xD7AF
        or 0x20 <= o <= 0x7E
    )


class ParseError(Exception):
    """Raised when a source file cannot be parsed into text."""


@dataclass(frozen=True)
class ParseOutcome:
    text: str
    route: str  # text | pymupdf | docling
    skeleton: bool | None = None
    skeleton_reason: str | None = None
    block_counts: dict[str, int] | None = None


class DocumentParser(Protocol):
    def parse_to_markdown(self, filename: str, data: bytes) -> str:
        """Return Markdown (or plain text). Empty string if no extractable text."""
        ...


def _decode_text(data: bytes) -> str:
    if not data:
        return ""
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ParseError("Unable to decode text bytes")


def _non_ws(s: str) -> str:
    return "".join(ch for ch in s if not ch.isspace())


@dataclass(frozen=True)
class PdfFastMetrics:
    page_count: int
    total_chars: int
    chars_per_page: float
    printable_ratio: float
    empty_page_ratio: float
    page_texts: tuple[str, ...]


def extract_pdf_pages_pymupdf(data: bytes) -> PdfFastMetrics:
    """Extract per-page text via PyMuPDF. Raises ParseError on open/extract failure."""
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise ParseError(
            "pymupdf is not installed; pip install pymupdf"
        ) from exc

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        raise ParseError(f"PyMuPDF failed to open PDF: {exc}") from exc

    try:
        page_texts: list[str] = []
        for page in doc:
            try:
                page_texts.append(page.get_text("text") or "")
            except Exception as exc:  # noqa: BLE001
                raise ParseError(f"PyMuPDF failed to extract page: {exc}") from exc
    finally:
        doc.close()

    page_count = max(len(page_texts), 1)
    per_page_nw = [_non_ws(t) for t in page_texts]
    total_chars = sum(len(p) for p in per_page_nw)
    empty_pages = sum(1 for p in per_page_nw if len(p) < 10)
    joined = "".join(per_page_nw)
    if total_chars == 0:
        printable_ratio = 1.0
    else:
        printable = sum(1 for ch in joined if _is_quality_char(ch))
        printable_ratio = printable / total_chars

    return PdfFastMetrics(
        page_count=page_count if page_texts else 0,
        total_chars=total_chars,
        chars_per_page=(total_chars / page_count) if page_texts else 0.0,
        printable_ratio=printable_ratio,
        empty_page_ratio=(empty_pages / page_count) if page_texts else 1.0,
        page_texts=tuple(page_texts),
    )


def pdf_fast_quality_ok(
    metrics: PdfFastMetrics,
    *,
    min_chars: int,
    min_chars_per_page: float,
    min_printable_ratio: float,
    max_empty_page_ratio: float,
) -> bool:
    """Return True if PyMuPDF extraction passes the quality gate."""
    if metrics.page_count <= 0:
        return False
    if metrics.total_chars < min_chars:
        return False
    if metrics.chars_per_page < min_chars_per_page:
        return False
    if metrics.printable_ratio < min_printable_ratio:
        return False
    if metrics.empty_page_ratio > max_empty_page_ratio:
        return False
    return True


class TextDocumentParser:
    """Decode .txt/.md; binary Office/PDF requires routed parser / Docling."""

    def parse_to_markdown(self, filename: str, data: bytes) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix in _TEXT_SUFFIXES:
            return _decode_text(data)
        if suffix == _PDF_SUFFIX or suffix in _OFFICE_SUFFIXES:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ParseError(
                    f"Cannot parse {suffix} without Docling; install rag-api[docling]"
                ) from exc
            if "\x00" in text[:4096]:
                raise ParseError(
                    f"Cannot parse {suffix} without Docling; install rag-api[docling]"
                )
            return text
        raise ParseError(f"Unsupported file type: {suffix or '(none)'}")


class DoclingDocumentParser:
    """Docling-backed parser: do_ocr=False, tables as Markdown."""

    def __init__(self) -> None:
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ImportError as exc:
            raise RuntimeError(
                "docling is not installed; pip install 'rag-api[docling]'"
            ) from exc

        pdf_opts = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_opts),
            }
        )
        self._text = TextDocumentParser()

    def parse_to_markdown(self, filename: str, data: bytes) -> str:
        blocks = self.parse_to_blocks(filename, data)
        return blocks_to_markdown(blocks)

    def parse_to_blocks(self, filename: str, data: bytes) -> list[ParseBlock]:
        suffix = Path(filename).suffix.lower()
        if suffix in _TEXT_SUFFIXES:
            md = self._text.parse_to_markdown(filename, data)
            return markdown_to_blocks(md)

        suffix_or = suffix if suffix else ".bin"
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix_or, delete=True) as tmp:
                tmp.write(data)
                tmp.flush()
                result = self._converter.convert(tmp.name)
                md = result.document.export_to_markdown()
                return markdown_to_blocks((md or "").strip())
        except ParseError:
            raise
        except Exception as exc:  # noqa: BLE001 — map to ParseError for job.failed
            logger.exception("Docling convert failed for %s", filename)
            raise ParseError(f"Docling failed to parse {filename}: {exc}") from exc


class RoutedDocumentParser:
    """F04 skeleton-aware dual-route parser with parse_route logging."""

    def __init__(
        self,
        *,
        docling: DocumentParser | None = None,
        settings: object | None = None,
    ) -> None:
        self._docling = docling
        self._settings = settings
        self._text = TextDocumentParser()
        self.last_routes: list[tuple[str, str]] = []
        self.last_skeleton: list[tuple[str, SkeletonProbe]] = []

    def _cfg(self) -> object:
        return self._settings or get_settings()

    def _get_docling(self) -> DocumentParser:
        if self._docling is not None:
            return self._docling
        try:
            self._docling = DoclingDocumentParser()
        except RuntimeError as exc:
            raise ParseError(str(exc)) from exc
        return self._docling

    def parse_outcome(self, filename: str, data: bytes) -> ParseOutcome:
        suffix = Path(filename).suffix.lower()
        if suffix in _TEXT_SUFFIXES:
            if suffix in {".txt", ".md"}:
                from rag_api.domain.documents.file_type import (
                    FileTypeError,
                    validate_file_type,
                )

                try:
                    validate_file_type(filename, data)
                except FileTypeError as exc:
                    raise ParseError(str(exc)) from exc
            outcome = ParseOutcome(text=_decode_text(data), route="text")
            self._log_route(filename, outcome.route, reason="text_suffix")
            return outcome

        if suffix == _PDF_SUFFIX:
            from rag_api.domain.documents.file_type import FileTypeError, validate_file_type

            try:
                validate_file_type(filename, data)
            except FileTypeError as exc:
                raise ParseError(str(exc)) from exc
            return self._parse_pdf(filename, data)

        if suffix in _OFFICE_SUFFIXES:
            return self._parse_office(filename, data)

        if suffix in _LEGACY_OFFICE_SUFFIXES:
            raise ParseError(f"Legacy Office format not supported: {suffix}")

        raise ParseError(f"Unsupported file type: {suffix or '(none)'}")

    def parse_to_markdown(self, filename: str, data: bytes) -> str:
        return self.parse_outcome(filename, data).text

    def _parse_office(self, filename: str, data: bytes) -> ParseOutcome:
        from rag_api.domain.documents.file_type import FileTypeError, validate_file_type
        from rag_api.indexing.office import OfficeParseError, office_to_markdown

        try:
            validate_file_type(filename, data)
        except FileTypeError as exc:
            raise ParseError(str(exc)) from exc

        suffix = Path(filename).suffix.lower()
        route = suffix.lstrip(".")  # docx | pptx | xlsx
        try:
            text = office_to_markdown(filename, data)
        except OfficeParseError as exc:
            raise ParseError(str(exc)) from exc

        outcome = ParseOutcome(
            text=text,
            route=route,
            skeleton=None,
        )
        self._log_route(filename, outcome.route, reason="office_lightweight")
        return outcome

    def _structure_via_docling(
        self, filename: str, data: bytes
    ) -> tuple[str, dict[str, int]]:
        parser = self._get_docling()
        if hasattr(parser, "parse_to_blocks"):
            blocks = parser.parse_to_blocks(filename, data)  # type: ignore[attr-defined]
            counts = count_block_kinds(blocks)
            return blocks_to_markdown(blocks), counts
        md = parser.parse_to_markdown(filename, data)
        blocks = markdown_to_blocks(md)
        return blocks_to_markdown(blocks), count_block_kinds(blocks)

    def _parse_pdf(self, filename: str, data: bytes) -> ParseOutcome:
        cfg = self._cfg()
        force = bool(getattr(cfg, "pdf_force_structure", False))

        try:
            metrics = extract_pdf_pages_pymupdf(data)
        except ParseError as exc:
            logger.info(
                "pdf_extract error filename=%s err=%s; trying docling",
                filename,
                exc,
            )
            text, counts = self._structure_via_docling(filename, data)
            outcome = ParseOutcome(
                text=text,
                route="docling",
                skeleton=True,
                skeleton_reason="pymupdf_error",
                block_counts=counts,
            )
            self._log_route(
                filename,
                outcome.route,
                reason="pymupdf_error",
                skeleton=True,
                skeleton_reason="pymupdf_error",
                block_counts=counts,
            )
            return outcome

        if metrics.total_chars == 0 and not force:
            outcome = ParseOutcome(
                text="",
                route="pymupdf",
                skeleton=False,
                skeleton_reason="empty",
            )
            self._log_route(
                filename,
                outcome.route,
                reason="empty_text_layer",
                metrics=metrics,
                skeleton=False,
                skeleton_reason="empty",
            )
            return outcome

        try:
            probe = detect_pdf_skeleton(
                data,
                min_toc=int(getattr(cfg, "pdf_skeleton_min_toc", 1)),
                min_heading_candidates=int(
                    getattr(cfg, "pdf_skeleton_min_heading_candidates", 3)
                ),
                force=force,
            )
        except RuntimeError as exc:
            raise ParseError(str(exc)) from exc

        self.last_skeleton.append((filename, probe))

        if probe.has_skeleton:
            text, counts = self._structure_via_docling(filename, data)
            outcome = ParseOutcome(
                text=text,
                route="docling",
                skeleton=True,
                skeleton_reason=probe.reason,
                block_counts=counts,
            )
            self._log_route(
                filename,
                outcome.route,
                reason=f"skeleton_{probe.reason}",
                metrics=metrics,
                skeleton=True,
                skeleton_reason=probe.reason,
                block_counts=counts,
            )
            return outcome

        ok = pdf_fast_quality_ok(
            metrics,
            min_chars=int(getattr(cfg, "pdf_fast_min_chars")),
            min_chars_per_page=float(getattr(cfg, "pdf_fast_min_chars_per_page")),
            min_printable_ratio=float(getattr(cfg, "pdf_fast_min_printable_ratio")),
            max_empty_page_ratio=float(getattr(cfg, "pdf_fast_max_empty_page_ratio")),
        )
        if ok:
            text = "\n\n".join(t.strip() for t in metrics.page_texts if t.strip())
            outcome = ParseOutcome(
                text=text,
                route="pymupdf",
                skeleton=False,
                skeleton_reason="none",
            )
            self._log_route(
                filename,
                outcome.route,
                reason="no_skeleton_quality_ok",
                metrics=metrics,
                skeleton=False,
                skeleton_reason="none",
            )
            return outcome

        logger.info(
            "pdf_no_skeleton quality_fail filename=%s; falling back to docling",
            filename,
        )
        text, counts = self._structure_via_docling(filename, data)
        outcome = ParseOutcome(
            text=text,
            route="docling",
            skeleton=False,
            skeleton_reason="none",
            block_counts=counts,
        )
        self._log_route(
            filename,
            outcome.route,
            reason="no_skeleton_quality_fail",
            metrics=metrics,
            skeleton=False,
            skeleton_reason="none",
            block_counts=counts,
        )
        return outcome

    def _log_route(
        self,
        filename: str,
        route: str,
        *,
        reason: str,
        metrics: PdfFastMetrics | None = None,
        skeleton: bool | None = None,
        skeleton_reason: str | None = None,
        block_counts: dict[str, int] | None = None,
    ) -> None:
        self.last_routes.append((filename, route))
        extra = ""
        if metrics is not None:
            extra += (
                f" pages={metrics.page_count} total_chars={metrics.total_chars} "
                f"cpp={metrics.chars_per_page:.1f} printable={metrics.printable_ratio:.3f} "
                f"empty_page_ratio={metrics.empty_page_ratio:.3f}"
            )
        if skeleton is not None:
            extra += f" skeleton={str(skeleton).lower()}"
        if skeleton_reason:
            extra += f" skeleton_reason={skeleton_reason}"
        if block_counts:
            extra += (
                f" headings={block_counts.get('heading', 0)}"
                f" tables={block_counts.get('table', 0)}"
                f" images={block_counts.get('image', 0)}"
            )
        logger.info(
            "parse_route=%s filename=%s reason=%s%s",
            route,
            filename,
            reason,
            extra,
        )


class ScriptedDocumentParser:
    """Test double: map filename → markdown (or raise)."""

    def __init__(
        self,
        mapping: dict[str, str] | None = None,
        *,
        default: str | None = None,
        fail_suffixes: frozenset[str] | None = None,
        empty_suffixes: frozenset[str] | None = None,
        route: str = "text",
    ) -> None:
        self._mapping = mapping or {}
        self._default = default
        self._fail_suffixes = fail_suffixes or frozenset()
        self._empty_suffixes = empty_suffixes or frozenset()
        self._route = route
        self.last_routes: list[tuple[str, str]] = []

    def parse_outcome(self, filename: str, data: bytes) -> ParseOutcome:
        text = self.parse_to_markdown(filename, data)
        outcome = ParseOutcome(text=text, route=self._route)
        self.last_routes.append((filename, outcome.route))
        return outcome

    def parse_to_markdown(self, filename: str, data: bytes) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix in self._fail_suffixes:
            raise ParseError(f"scripted failure for {filename}")
        if suffix in self._empty_suffixes:
            return ""
        if filename in self._mapping:
            return self._mapping[filename]
        if self._default is not None:
            return self._default
        return TextDocumentParser().parse_to_markdown(filename, data)


def get_document_parser() -> DocumentParser:
    return RoutedDocumentParser()


def parse_files_to_markdown(
    files: list[tuple[str, bytes]],
    *,
    parser: DocumentParser | None = None,
) -> str:
    """Parse multiple (filename, bytes) in order; join with separator."""
    parser = parser or get_document_parser()
    parts: list[str] = []
    for filename, data in files:
        if hasattr(parser, "parse_outcome"):
            outcome = parser.parse_outcome(filename, data)  # type: ignore[attr-defined]
            md = outcome.text
        else:
            md = parser.parse_to_markdown(filename, data)
        if md.strip():
            parts.append(md.strip())
    return _FILE_SEPARATOR.join(parts)
