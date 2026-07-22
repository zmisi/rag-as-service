"""Unit tests for Phase 1 allowed document extensions."""

from rag_api.domain.documents.constants import (
    file_type_reject_message,
    is_allowed_extension,
    is_legacy_extension,
)


def test_allows_ooxml_and_text_pdf():
    for name in ("a.txt", "b.PDF", "c.docx", "d.PPTX"):
        assert is_allowed_extension(name), name
        assert not is_legacy_extension(name), name


def test_rejects_legacy_doc_ppt():
    for name in ("legacy.doc", "slides.PPT"):
        assert not is_allowed_extension(name), name
        assert is_legacy_extension(name), name
        msg = file_type_reject_message(name).lower()
        assert "docx" in msg and "pptx" in msg


def test_rejects_other_types():
    assert not is_allowed_extension("malware.exe")
    assert not is_legacy_extension("malware.exe")
    assert "unsupported" in file_type_reject_message("malware.exe").lower()


def test_docx_not_treated_as_legacy_doc():
    assert is_allowed_extension("report.docx")
    assert not is_legacy_extension("report.docx")
