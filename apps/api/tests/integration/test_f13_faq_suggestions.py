"""F13 Portal FAQ suggestion API test cases (F13-T01 … F13-T07)."""

from __future__ import annotations

import io

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_api.db.models import FaqSuggestionStats
from tests.helpers import (
    issue_session_for_user,
    set_client_session_cookie,
    tenant_host_headers,
)

HEADERS_A = tenant_host_headers("pytest-a")
HEADERS_B = tenant_host_headers("pytest-b")
TXT_BODY = b"FAQ answer body for tests.\n"


def _create_upload_publish(client, headers, *, title: str, tag: str = "faq") -> dict:
    created = client.post("/v1/documents", headers=headers)
    assert created.status_code == 201, created.text
    doc_id = created.json()["id"]
    up = client.post(
        f"/v1/documents/{doc_id}/files",
        headers=headers,
        files={"file": ("note.txt", io.BytesIO(TXT_BODY), "text/plain")},
    )
    assert up.status_code == 201, up.text
    client.patch(
        f"/v1/documents/{doc_id}",
        json={"title": title, "tag": tag},
        headers=headers,
    )
    client.post(f"/v1/documents/{doc_id}/submit-review", headers=headers)
    pub = client.post(f"/v1/documents/{doc_id}/publish", headers=headers)
    assert pub.status_code == 200, pub.text
    return pub.json()


def _set_clicks(db: Session, *, tenant_id, document_group_id, click_count: int) -> None:
    stats = db.scalar(
        select(FaqSuggestionStats).where(
            FaqSuggestionStats.tenant_id == tenant_id,
            FaqSuggestionStats.document_group_id == document_group_id,
        )
    )
    if stats is None:
        stats = FaqSuggestionStats(
            tenant_id=tenant_id,
            document_group_id=document_group_id,
            click_count=click_count,
        )
        db.add(stats)
    else:
        stats.click_count = click_count
    db.commit()


@pytest.mark.integration
def test_f13_t01_t02_top5_sorted_hot(
    client_a, tenants: dict, db: Session
):
    """F13-T01/T02: ≥5 FAQs → 5 items, click_count desc, first hot."""
    docs = []
    for i in range(6):
        docs.append(
            _create_upload_publish(client_a, HEADERS_A, title=f"FAQ {i}")
        )
    # Make FAQ 3 hottest, then FAQ 1
    _set_clicks(
        db,
        tenant_id=tenants["tenant_a"].tenant_id,
        document_group_id=docs[3]["document_group_id"],
        click_count=50,
    )
    _set_clicks(
        db,
        tenant_id=tenants["tenant_a"].tenant_id,
        document_group_id=docs[1]["document_group_id"],
        click_count=20,
    )

    resp = client_a.get("/v1/portal/faq-suggestions", headers=HEADERS_A)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 5
    assert body[0]["hot"] is True
    assert all(item["hot"] is False for item in body[1:])
    assert body[0]["document_group_id"] == docs[3]["document_group_id"]
    assert body[0]["click_count"] == 50
    assert body[1]["document_group_id"] == docs[1]["document_group_id"]
    clicks = [item["click_count"] for item in body]
    assert clicks == sorted(clicks, reverse=True)


@pytest.mark.integration
def test_f13_t03_click_increments(client_a, tenants: dict, db: Session):
    """F13-T03: click → click_count+1 and question text returned."""
    doc = _create_upload_publish(client_a, HEADERS_A, title="How to reset?")
    group_id = doc["document_group_id"]
    before = client_a.get("/v1/portal/faq-suggestions", headers=HEADERS_A).json()
    assert before[0]["click_count"] == 0

    clicked = client_a.post(
        f"/v1/portal/faq-suggestions/{group_id}/click", headers=HEADERS_A
    )
    assert clicked.status_code == 200, clicked.text
    payload = clicked.json()
    assert payload["question"] == "How to reset?"
    assert payload["click_count"] == 1

    after = client_a.get("/v1/portal/faq-suggestions", headers=HEADERS_A).json()
    assert after[0]["click_count"] == 1
    stats = db.scalar(
        select(FaqSuggestionStats).where(
            FaqSuggestionStats.tenant_id == tenants["tenant_a"].tenant_id,
            FaqSuggestionStats.document_group_id == group_id,
        )
    )
    assert stats is not None
    assert stats.click_count == 1


@pytest.mark.integration
def test_f13_t04_refresh_batch(client_a, db: Session, tenants: dict):
    """F13-T04: offset page advances; new first item is hot."""
    docs = [
        _create_upload_publish(client_a, HEADERS_A, title=f"Batch FAQ {i}")
        for i in range(7)
    ]
    for i, doc in enumerate(docs):
        _set_clicks(
            db,
            tenant_id=tenants["tenant_a"].tenant_id,
            document_group_id=doc["document_group_id"],
            click_count=100 - i,
        )

    first = client_a.get(
        "/v1/portal/faq-suggestions", params={"offset": 0}, headers=HEADERS_A
    ).json()
    second = client_a.get(
        "/v1/portal/faq-suggestions", params={"offset": 5}, headers=HEADERS_A
    ).json()
    assert len(first) == 5
    assert first[0]["hot"] is True
    assert second[0]["hot"] is True
    assert first[0]["document_group_id"] != second[0]["document_group_id"]
    # Remaining 2 + cycle into first of ranked list
    assert len(second) == 5


@pytest.mark.integration
def test_f13_t05_fewer_than_page(client_a):
    """F13-T05: only 2 FAQs → return 2, no 500."""
    _create_upload_publish(client_a, HEADERS_A, title="One")
    _create_upload_publish(client_a, HEADERS_A, title="Two")
    resp = client_a.get("/v1/portal/faq-suggestions", headers=HEADERS_A)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.integration
def test_f13_t06_excludes_draft_and_non_faq(client_a):
    """F13-T06: draft / non-faq not in suggestions."""
    _create_upload_publish(client_a, HEADERS_A, title="Visible FAQ", tag="faq")
    created = client_a.post("/v1/documents", headers=HEADERS_A)
    doc_id = created.json()["id"]
    client_a.post(
        f"/v1/documents/{doc_id}/files",
        headers=HEADERS_A,
        files={"file": ("note.txt", io.BytesIO(TXT_BODY), "text/plain")},
    )
    client_a.patch(
        f"/v1/documents/{doc_id}",
        json={"title": "Draft FAQ", "tag": "faq"},
        headers=HEADERS_A,
    )
    _create_upload_publish(client_a, HEADERS_A, title="SOP doc", tag="sop")

    body = client_a.get("/v1/portal/faq-suggestions", headers=HEADERS_A).json()
    questions = {item["question"] for item in body}
    assert questions == {"Visible FAQ"}


@pytest.mark.integration
def test_f13_t07_tenant_isolation(client_a, switch_to_b, tenants: dict, db: Session):
    """F13-T07: tenant-B cannot see tenant-A FAQ or heat."""
    doc = _create_upload_publish(client_a, HEADERS_A, title="Tenant A FAQ")
    _set_clicks(
        db,
        tenant_id=tenants["tenant_a"].tenant_id,
        document_group_id=doc["document_group_id"],
        click_count=9,
    )

    client_b = switch_to_b()
    body_b = client_b.get("/v1/portal/faq-suggestions", headers=HEADERS_B).json()
    assert all(item["question"] != "Tenant A FAQ" for item in body_b)
    click_b = client_b.post(
        f"/v1/portal/faq-suggestions/{doc['document_group_id']}/click",
        headers=HEADERS_B,
    )
    assert click_b.status_code == 404

    # Switch back to A: heat unchanged by B's failed click
    token = issue_session_for_user(db, tenants["user_a"].user_id)
    set_client_session_cookie(client_a, token, host=HEADERS_A["Host"])
    body_a = client_a.get("/v1/portal/faq-suggestions", headers=HEADERS_A).json()
    assert body_a[0]["question"] == "Tenant A FAQ"
    assert body_a[0]["click_count"] == 9
