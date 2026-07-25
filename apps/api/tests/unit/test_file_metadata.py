"""Unit tests for file_metadata schema_version=1 helpers."""

from __future__ import annotations

import io

from rag_api.ingestion.file_metadata import (
    apply_modified_at_from_metadata,
    build_upload_metadata,
    extract_document_properties,
    merge_file_metadata,
)


def test_build_upload_metadata_shape() -> None:
    meta = build_upload_metadata(
        filename="a.pdf",
        content_type="application/pdf",
        size_bytes=12,
        uploaded_at="2026-07-25T02:00:00Z",
    )
    assert meta["schema_version"] == 1
    assert meta["upload"]["original_filename"] == "a.pdf"
    assert meta["upload"]["size_bytes"] == 12
    assert meta["upload"]["declared_content_type"] == "application/pdf"
    assert meta["upload"]["uploaded_at"] == "2026-07-25T02:00:00Z"


def test_merge_preserves_upload_adds_document() -> None:
    base = build_upload_metadata(
        filename="a.pdf", content_type="application/pdf", size_bytes=1
    )
    merged = merge_file_metadata(base, document={"page_count": 3, "title": "T"})
    assert merged["upload"]["original_filename"] == "a.pdf"
    assert merged["document"]["page_count"] == 3
    assert merged["document"]["title"] == "T"


def test_extract_pdf_page_count() -> None:
    # Minimal one-page PDF
    data = b"""%PDF-1.1
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 3 3] >>endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer<< /Size 4 /Root 1 0 R >>
startxref
190
%%EOF"""
    props = extract_document_properties("x.pdf", data)
    assert props.get("page_count") == 1


def test_extract_docx_title() -> None:
    from docx import Document

    doc = Document()
    doc.core_properties.title = "HelloDoc"
    doc.add_paragraph("body")
    buf = io.BytesIO()
    doc.save(buf)
    props = extract_document_properties("x.docx", buf.getvalue())
    assert props.get("title") == "HelloDoc"


def test_apply_modified_at_prefers_document() -> None:
    meta = {
        "schema_version": 1,
        "upload": {"uploaded_at": "2026-01-01T00:00:00Z"},
        "document": {"modified_at": "2026-06-01T12:00:00Z"},
    }
    dt = apply_modified_at_from_metadata(meta)
    assert dt is not None
    assert dt.year == 2026 and dt.month == 6
