"""F04temp integration: index + pgvector search (requires DATABASE_URL)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from rag_api.db.models import Document, DocumentFile, IndexJob, Tenant, TenantMember, User
from rag_api.indexing.embedding import HashingEmbedder
from rag_api.indexing.search import PgKnowledgeSearcher
from rag_api.indexing.worker import process_index_job
from rag_api.services.storage_service import StorageService


@pytest.mark.integration
def test_f04temp_index_and_search_phrase(db: Session, tmp_path) -> None:
    password = "x"
    tenant = Tenant(subdomain=f"t-{uuid4().hex[:8]}", display_name="t")
    user = User(email=f"u-{uuid4().hex[:8]}@example.com", password_hash=password)
    db.add_all([tenant, user])
    db.flush()
    db.add(TenantMember(tenant_id=tenant.id, user_id=user.id, role="owner"))

    doc = Document(
        tenant_id=tenant.id,
        created_by=user.id,
        title="退货",
        tag="faq",
        status="published",
        version="1.0",
    )
    db.add(doc)
    db.flush()

    storage = StorageService(root=tmp_path)
    key = storage.storage_key(
        tenant_id=tenant.id, document_id=doc.id, version="1.0", filename="p.txt"
    )
    storage.write_bytes(key, "客户可在收货后 30 天内申请退货。".encode("utf-8"))
    db.add(
        DocumentFile(
            tenant_id=tenant.id,
            document_id=doc.id,
            version="1.0",
            storage_key=key,
            filename="p.txt",
            content_type="text/plain",
            size_bytes=40,
        )
    )
    job = IndexJob(
        tenant_id=tenant.id,
        document_id=doc.id,
        version="1.0",
        status="pending",
    )
    db.add(job)
    db.commit()

    emb = HashingEmbedder()
    process_index_job(db, job.id, embedder=emb, storage=storage)
    db.refresh(job)
    assert job.status == "succeeded"

    count = db.execute(
        text(
            "SELECT count(*) FROM rag_service.document_chunks "
            "WHERE document_id = CAST(:id AS uuid) AND is_active"
        ),
        {"id": str(doc.id)},
    ).scalar()
    assert int(count or 0) >= 1

    def _factory():
        return db

    searcher = PgKnowledgeSearcher(_factory, embedder=emb)
    hits = searcher.search(tenant.id, "退货窗口 30 天", top_k=3)
    assert hits
    assert any("30" in h.content for h in hits)
