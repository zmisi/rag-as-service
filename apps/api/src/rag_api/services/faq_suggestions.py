"""Portal FAQ suggestions (F13)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_api.db.models import Document, FaqSuggestionStats

FAQ_PAGE_SIZE = 5


@dataclass
class FaqSuggestionItem:
    document_group_id: UUID
    document_id: UUID
    question: str
    click_count: int
    hot: bool


def _click_map(db: Session, *, tenant_id: UUID, group_ids: list[UUID]) -> dict[UUID, int]:
    if not group_ids:
        return {}
    rows = db.scalars(
        select(FaqSuggestionStats).where(
            FaqSuggestionStats.tenant_id == tenant_id,
            FaqSuggestionStats.document_group_id.in_(group_ids),
        )
    ).all()
    return {r.document_group_id: r.click_count for r in rows}


def list_faq_candidates(db: Session, *, tenant_id: UUID) -> list[tuple[Document, int]]:
    """Published latest FAQ docs with click_count, hottest first."""
    docs = list(
        db.scalars(
            select(Document).where(
                Document.tenant_id == tenant_id,
                Document.deleted_at.is_(None),
                Document.is_latest.is_(True),
                Document.publish_status == "published",
                Document.doc_tag == "faq",
            )
        ).all()
    )
    clicks = _click_map(db, tenant_id=tenant_id, group_ids=[d.doc_group_id for d in docs])
    ranked = [(d, clicks.get(d.doc_group_id, 0)) for d in docs]
    ranked.sort(key=lambda item: (-item[1], item[0].doc_name.lower(), str(item[0].doc_group_id)))
    return ranked


def list_faq_suggestions(
    db: Session,
    *,
    tenant_id: UUID,
    offset: int = 0,
) -> list[FaqSuggestionItem]:
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be >= 0")
    ranked = list_faq_candidates(db, tenant_id=tenant_id)
    if not ranked:
        return []
    n = len(ranked)
    start = offset % n
    window: list[tuple[Document, int]] = []
    for i in range(min(FAQ_PAGE_SIZE, n)):
        window.append(ranked[(start + i) % n])
    items: list[FaqSuggestionItem] = []
    for idx, (doc, click_count) in enumerate(window):
        question = (doc.doc_name or "").strip() or "未命名问题"
        items.append(
            FaqSuggestionItem(
                document_group_id=doc.doc_group_id,
                document_id=doc.doc_id,
                question=question,
                click_count=click_count,
                hot=idx == 0,
            )
        )
    return items


def click_faq_suggestion(
    db: Session,
    *,
    tenant_id: UUID,
    document_group_id: UUID,
) -> FaqSuggestionItem:
    ranked = list_faq_candidates(db, tenant_id=tenant_id)
    match = next((item for item in ranked if item[0].doc_group_id == document_group_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="FAQ suggestion not found")
    doc, _ = match
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
            click_count=0,
        )
        db.add(stats)
        db.flush()
    stats.click_count += 1
    db.commit()
    db.refresh(stats)
    question = (doc.doc_name or "").strip() or "未命名问题"
    return FaqSuggestionItem(
        document_group_id=doc.doc_group_id,
        document_id=doc.doc_id,
        question=question,
        click_count=stats.click_count,
        hot=False,
    )
