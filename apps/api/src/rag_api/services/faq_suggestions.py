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
    """One FAQ portal suggestion with click stats and hot flag."""

    document_group_id: UUID
    document_id: UUID
    question: str
    click_count: int
    hot: bool


@dataclass
class _Candidate:
    doc: Document
    click_count: int
    is_hot: bool


def _stats_map(
    db: Session, *, tenant_id: UUID, group_ids: list[UUID]
) -> dict[UUID, FaqSuggestionStats]:
    if not group_ids:
        return {}
    rows = db.scalars(
        select(FaqSuggestionStats).where(
            FaqSuggestionStats.tenant_id == tenant_id,
            FaqSuggestionStats.document_group_id.in_(group_ids),
        )
    ).all()
    return {r.document_group_id: r for r in rows}


def list_faq_candidates(db: Session, *, tenant_id: UUID) -> list[_Candidate]:
    """Published latest FAQ docs with click_count and is_hot."""
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
    stats = _stats_map(db, tenant_id=tenant_id, group_ids=[d.doc_group_id for d in docs])
    ranked: list[_Candidate] = []
    for d in docs:
        row = stats.get(d.doc_group_id)
        ranked.append(
            _Candidate(
                doc=d,
                click_count=row.click_count if row is not None else 0,
                is_hot=bool(row.is_hot) if row is not None else False,
            )
        )

    def sort_key(item: _Candidate) -> tuple:
        return (-item.click_count, item.doc.doc_name.lower(), str(item.doc.doc_group_id))

    hots = sorted([c for c in ranked if c.is_hot], key=sort_key)
    normals = sorted([c for c in ranked if not c.is_hot], key=sort_key)
    return hots + normals


def list_faq_suggestions(
    db: Session,
    *,
    tenant_id: UUID,
    offset: int = 0,
) -> list[FaqSuggestionItem]:
    """Return a rotating page of FAQ suggestions starting at ``offset``."""
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be >= 0")
    ranked = list_faq_candidates(db, tenant_id=tenant_id)
    if not ranked:
        return []

    hots = [c for c in ranked if c.is_hot]
    normals = [c for c in ranked if not c.is_hot]
    normals_page = max(0, FAQ_PAGE_SIZE - len(hots))

    window: list[_Candidate] = list(hots)
    if normals and normals_page > 0:
        n = len(normals)
        start = offset % n
        for i in range(min(normals_page, n)):
            window.append(normals[(start + i) % n])

    items: list[FaqSuggestionItem] = []
    for c in window:
        question = (c.doc.doc_name or "").strip() or "未命名问题"
        items.append(
            FaqSuggestionItem(
                document_group_id=c.doc.doc_group_id,
                document_id=c.doc.doc_id,
                question=question,
                click_count=c.click_count,
                hot=c.is_hot,
            )
        )
    return items


def click_faq_suggestion(
    db: Session,
    *,
    tenant_id: UUID,
    document_group_id: UUID,
) -> FaqSuggestionItem:
    """Increment click count for an FAQ doc group; 404 if not a candidate."""
    ranked = list_faq_candidates(db, tenant_id=tenant_id)
    match = next((c for c in ranked if c.doc.doc_group_id == document_group_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="FAQ suggestion not found")
    doc = match.doc
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
            is_hot=False,
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
        hot=bool(stats.is_hot),
    )
