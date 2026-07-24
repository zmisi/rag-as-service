"""F13 Portal FAQ suggestion API test cases (F13-T01 … F13-T07)."""

from __future__ import annotations

import io
from uuid import UUID

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


def _set_stats(
    db: Session,
    *,
    tenant_id: UUID,
    document_group_id: UUID,
    click_count: int = 0,
    is_hot: bool = False,
) -> None:
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
            is_hot=is_hot,
        )
        db.add(stats)
    else:
        stats.click_count = click_count
        stats.is_hot = is_hot
    db.commit()


@pytest.mark.integration
def test_f13_t01_five_with_two_hot(client_a, tenants: dict, db: Session):
    """F13-T01: ≥5 FAQs with 2 is_hot → 5 items; first 2 hot, rest not."""
    docs = [
        _create_upload_publish(client_a, HEADERS_A, title=f"FAQ {i}") for i in range(6)
    ]
    tenant_id = tenants["tenant_a"].tenant_id
    _set_stats(
        db,
        tenant_id=tenant_id,
        document_group_id=docs[3]["document_group_id"],
        is_hot=True,
        click_count=1,
    )
    _set_stats(
        db,
        tenant_id=tenant_id,
        document_group_id=docs[1]["document_group_id"],
        is_hot=True,
        click_count=2,
    )

    resp = client_a.get("/v1/portal/faq-suggestions", headers=HEADERS_A)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 5
    assert body[0]["hot"] is True
    assert body[1]["hot"] is True
    assert all(item["hot"] is False for item in body[2:])
    hot_ids = {body[0]["document_group_id"], body[1]["document_group_id"]}
    assert hot_ids == {
        docs[1]["document_group_id"],
        docs[3]["document_group_id"],
    }
    # Among hots, higher click_count first
    assert body[0]["document_group_id"] == docs[1]["document_group_id"]


@pytest.mark.integration
def test_f13_t02_hot_beats_higher_clicks(client_a, tenants: dict, db: Session):
    """F13-T02: is_hot ranks above non-hot even when non-hot has more clicks."""
    hot_doc = _create_upload_publish(client_a, HEADERS_A, title="Marked Hot")
    cold_doc = _create_upload_publish(client_a, HEADERS_A, title="High Clicks")
    tenant_id = tenants["tenant_a"].tenant_id
    _set_stats(
        db,
        tenant_id=tenant_id,
        document_group_id=hot_doc["document_group_id"],
        is_hot=True,
        click_count=1,
    )
    _set_stats(
        db,
        tenant_id=tenant_id,
        document_group_id=cold_doc["document_group_id"],
        is_hot=False,
        click_count=99,
    )

    body = client_a.get("/v1/portal/faq-suggestions", headers=HEADERS_A).json()
    assert body[0]["document_group_id"] == hot_doc["document_group_id"]
    assert body[0]["hot"] is True
    assert body[1]["document_group_id"] == cold_doc["document_group_id"]
    assert body[1]["hot"] is False


@pytest.mark.integration
def test_f13_t03_click_increments(client_a, tenants: dict, db: Session):
    """F13-T03: click → click_count+1; is_hot unchanged; question returned."""
    doc = _create_upload_publish(client_a, HEADERS_A, title="How to reset?")
    group_id = doc["document_group_id"]
    _set_stats(
        db,
        tenant_id=tenants["tenant_a"].tenant_id,
        document_group_id=group_id,
        is_hot=True,
        click_count=0,
    )
    before = client_a.get("/v1/portal/faq-suggestions", headers=HEADERS_A).json()
    assert before[0]["click_count"] == 0
    assert before[0]["hot"] is True

    clicked = client_a.post(
        f"/v1/portal/faq-suggestions/{group_id}/click", headers=HEADERS_A
    )
    assert clicked.status_code == 200, clicked.text
    payload = clicked.json()
    assert payload["question"] == "How to reset?"
    assert payload["click_count"] == 1
    assert payload["hot"] is True

    after = client_a.get("/v1/portal/faq-suggestions", headers=HEADERS_A).json()
    assert after[0]["click_count"] == 1
    assert after[0]["hot"] is True
    stats = db.scalar(
        select(FaqSuggestionStats).where(
            FaqSuggestionStats.tenant_id == tenants["tenant_a"].tenant_id,
            FaqSuggestionStats.document_group_id == group_id,
        )
    )
    assert stats is not None
    assert stats.click_count == 1
    assert stats.is_hot is True


@pytest.mark.integration
def test_f13_t04_refresh_batch_keeps_hot(client_a, db: Session, tenants: dict):
    """F13-T04: refresh rotates non-hot only; hot stays first."""
    docs = [
        _create_upload_publish(client_a, HEADERS_A, title=f"Batch FAQ {i}")
        for i in range(7)
    ]
    tenant_id = tenants["tenant_a"].tenant_id
    hot_a = docs[0]
    hot_b = docs[1]
    _set_stats(
        db,
        tenant_id=tenant_id,
        document_group_id=hot_a["document_group_id"],
        is_hot=True,
        click_count=10,
    )
    _set_stats(
        db,
        tenant_id=tenant_id,
        document_group_id=hot_b["document_group_id"],
        is_hot=True,
        click_count=5,
    )
    for i, doc in enumerate(docs[2:]):
        _set_stats(
            db,
            tenant_id=tenant_id,
            document_group_id=doc["document_group_id"],
            click_count=100 - i,
            is_hot=False,
        )

    first = client_a.get(
        "/v1/portal/faq-suggestions", params={"offset": 0}, headers=HEADERS_A
    ).json()
    # normals_page = 3; advance by 3
    second = client_a.get(
        "/v1/portal/faq-suggestions", params={"offset": 3}, headers=HEADERS_A
    ).json()
    assert len(first) == 5
    assert first[0]["hot"] is True and first[1]["hot"] is True
    assert second[0]["hot"] is True and second[1]["hot"] is True
    assert first[0]["document_group_id"] == second[0]["document_group_id"]
    assert first[1]["document_group_id"] == second[1]["document_group_id"]
    first_normals = {item["document_group_id"] for item in first[2:]}
    second_normals = {item["document_group_id"] for item in second[2:]}
    assert first_normals != second_normals
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
    _set_stats(
        db,
        tenant_id=tenants["tenant_a"].tenant_id,
        document_group_id=doc["document_group_id"],
        click_count=9,
        is_hot=True,
    )

    client_b = switch_to_b()
    body_b = client_b.get("/v1/portal/faq-suggestions", headers=HEADERS_B).json()
    assert all(item["question"] != "Tenant A FAQ" for item in body_b)
    click_b = client_b.post(
        f"/v1/portal/faq-suggestions/{doc['document_group_id']}/click",
        headers=HEADERS_B,
    )
    assert click_b.status_code == 404

    token = issue_session_for_user(db, tenants["user_a"].user_id)
    set_client_session_cookie(client_a, token, host=HEADERS_A["Host"])
    body_a = client_a.get("/v1/portal/faq-suggestions", headers=HEADERS_A).json()
    assert body_a[0]["question"] == "Tenant A FAQ"
    assert body_a[0]["click_count"] == 9
    assert body_a[0]["hot"] is True
