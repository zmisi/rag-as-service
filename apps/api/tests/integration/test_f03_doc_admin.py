"""F03 document admin integration tests."""

from __future__ import annotations

import io

import pytest
from sqlalchemy import delete, select

from rag_api.db.models import Document, DocumentFile, IndexJob
from tests.helpers import tenant_host_headers

HEADERS_A = tenant_host_headers("tenant-a")
HEADERS_B = tenant_host_headers("tenant-b")

PDF_BYTES = b"%PDF-1.4 minimal test content"


@pytest.fixture(autouse=True)
def wipe_documents(db):
    db.execute(delete(IndexJob))
    db.execute(delete(DocumentFile))
    db.execute(delete(Document))
    db.commit()


def _create_doc(client) -> str:
    r = client.post("/v1/documents", headers=HEADERS_A)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload_pdf(client, doc_id: str) -> None:
    r = client.post(
        f"/v1/documents/{doc_id}/files",
        headers=HEADERS_A,
        files={"file": ("sample.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert r.status_code == 201, r.text


def test_f03_t01_save_draft_with_pdf(client_a, db):
    doc_id = _create_doc(client_a)
    _upload_pdf(client_a, doc_id)
    r = client_a.patch(
        f"/v1/documents/{doc_id}",
        json={"title": "Manual", "tag": "faq"},
        headers=HEADERS_A,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert len(body["files"]) == 1
    assert body["files"][0]["filename"] == "sample.pdf"


def test_f03_t02_draft_cannot_publish(client_a):
    doc_id = _create_doc(client_a)
    r = client_a.post(f"/v1/documents/{doc_id}/publish", headers=HEADERS_A)
    assert r.status_code == 409
    doc = client_a.get(f"/v1/documents/{doc_id}", headers=HEADERS_A).json()
    assert doc["status"] == "draft"


def test_f03_t03_submit_review_missing_title(client_a):
    doc_id = _create_doc(client_a)
    _upload_pdf(client_a, doc_id)
    client_a.patch(
        f"/v1/documents/{doc_id}",
        json={"tag": "faq"},
        headers=HEADERS_A,
    )
    r = client_a.post(f"/v1/documents/{doc_id}/submit-review", headers=HEADERS_A)
    assert r.status_code == 400
    doc = client_a.get(f"/v1/documents/{doc_id}", headers=HEADERS_A).json()
    assert doc["status"] == "draft"


def test_f03_t04_submit_review_success(client_a):
    doc_id = _create_doc(client_a)
    _upload_pdf(client_a, doc_id)
    client_a.patch(
        f"/v1/documents/{doc_id}",
        json={"title": "FAQ doc", "tag": "faq"},
        headers=HEADERS_A,
    )
    r = client_a.post(f"/v1/documents/{doc_id}/submit-review", headers=HEADERS_A)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "review"


def test_f03_t05_publish_creates_index_job(client_a, db):
    doc_id = _create_doc(client_a)
    _upload_pdf(client_a, doc_id)
    client_a.patch(
        f"/v1/documents/{doc_id}",
        json={"title": "Publish me", "tag": "news"},
        headers=HEADERS_A,
    )
    client_a.post(f"/v1/documents/{doc_id}/submit-review", headers=HEADERS_A)
    r = client_a.post(f"/v1/documents/{doc_id}/publish", headers=HEADERS_A)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "published"
    assert body["version"] == "1.0"
    job = db.scalar(
        select(IndexJob).where(IndexJob.document_id == doc_id)
    )
    assert job is not None
    assert job.status == "pending"
    assert job.version == "1.0"


def test_f03_t06_unknown_tag_on_save(client_a):
    doc_id = _create_doc(client_a)
    r = client_a.patch(
        f"/v1/documents/{doc_id}",
        json={"tag": "unknown"},
        headers=HEADERS_A,
    )
    assert r.status_code == 400


def test_f03_t07_reject_exe_upload(client_a):
    doc_id = _create_doc(client_a)
    r = client_a.post(
        f"/v1/documents/{doc_id}/files",
        headers=HEADERS_A,
        files={"file": ("malware.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
    )
    assert r.status_code == 400


def test_f03_t07b_reject_legacy_doc_ppt(client_a):
    doc_id = _create_doc(client_a)
    for name, payload in (
        ("legacy.doc", b"OLE"),
        ("legacy.ppt", b"OLE"),
    ):
        r = client_a.post(
            f"/v1/documents/{doc_id}/files",
            headers=HEADERS_A,
            files={"file": (name, io.BytesIO(payload), "application/octet-stream")},
        )
        assert r.status_code == 400, name
        detail = r.json()["detail"]
        assert "docx" in detail.lower() and "pptx" in detail.lower(), detail


def test_f03_t08_reject_oversized_file(client_a):
    doc_id = _create_doc(client_a)
    big = b"x" * (20 * 1024 * 1024 + 1)
    r = client_a.post(
        f"/v1/documents/{doc_id}/files",
        headers=HEADERS_A,
        files={"file": ("big.pdf", io.BytesIO(big), "application/pdf")},
    )
    assert r.status_code == 400


def test_f03_t09_cross_tenant_get(client_a, switch_to_b):
    doc_id = _create_doc(client_a)
    client_b = switch_to_b()
    r = client_b.get(f"/v1/documents/{doc_id}", headers=HEADERS_B)
    assert r.status_code == 404


def test_f03_t10_new_version_publish(client_a):
    doc_id = _create_doc(client_a)
    _upload_pdf(client_a, doc_id)
    client_a.patch(
        f"/v1/documents/{doc_id}",
        json={"title": "V1", "tag": "knowledge_base"},
        headers=HEADERS_A,
    )
    client_a.post(f"/v1/documents/{doc_id}/submit-review", headers=HEADERS_A)
    client_a.post(f"/v1/documents/{doc_id}/publish", headers=HEADERS_A)

    client_a.post(f"/v1/documents/{doc_id}/new-version", headers=HEADERS_A)
    client_a.patch(
        f"/v1/documents/{doc_id}",
        json={"title": "V2"},
        headers=HEADERS_A,
    )
    client_a.post(f"/v1/documents/{doc_id}/submit-review", headers=HEADERS_A)
    r = client_a.post(f"/v1/documents/{doc_id}/publish", headers=HEADERS_A)
    assert r.status_code == 200, r.text
    assert r.json()["version"] == "1.1"


def test_f03_t11_list_filter_by_tag(client_a):
    doc_faq = _create_doc(client_a)
    _upload_pdf(client_a, doc_faq)
    client_a.patch(
        f"/v1/documents/{doc_faq}",
        json={"title": "FAQ one", "tag": "faq"},
        headers=HEADERS_A,
    )

    doc_news = _create_doc(client_a)
    _upload_pdf(client_a, doc_news)
    client_a.patch(
        f"/v1/documents/{doc_news}",
        json={"title": "News one", "tag": "news"},
        headers=HEADERS_A,
    )

    r = client_a.get("/v1/documents?tag=faq", headers=HEADERS_A)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["tag"] == "faq"
