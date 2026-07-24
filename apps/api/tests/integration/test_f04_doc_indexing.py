"""F04 integration tests (requires DATABASE_URL). Uses ScriptedDocumentParser."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from rag_api.db.models import Document, DocumentFile, IndexJob, Tenant, TenantMember, User
from rag_api.indexing.embedding import HashingEmbedder
from rag_api.indexing.parse import ScriptedDocumentParser
from rag_api.indexing.search import PgKnowledgeSearcher
from rag_api.indexing.worker import process_index_job
from rag_api.services.storage_service import StorageService


def _seed_tenant(db: Session) -> tuple[Tenant, User]:
    uname = f"u{uuid4().hex[:10]}"
    tname = f"t-{uuid4().hex[:8]}"
    tenant = Tenant(tenant_name=tname)
    user = User(email=f"{uname}@example.com", password_hash="x", user_name=uname)
    db.add_all([tenant, user])
    db.flush()
    db.add(
        TenantMember(
            tenant_id=tenant.tenant_id,
            user_id=user.user_id,
            member_name=uname,
            role="owner",
        )
    )
    return tenant, user


def _published_doc_with_file(
    db: Session,
    storage: StorageService,
    *,
    tenant: Tenant,
    user: User,
    filename: str = "p.txt",
    body: bytes = b"hello",
    version: int = 1,
    doc_group_id=None,
    is_latest: bool = True,
) -> tuple[Document, IndexJob]:
    group_id = doc_group_id or uuid4()
    doc = Document(
        tenant_id=tenant.tenant_id,
        created_by=user.user_id,
        doc_group_id=group_id,
        doc_name="退货",
        doc_tag="faq",
        publish_status="published",
        index_status="pending",
        version_number=version,
        is_latest=is_latest,
        source_metadata={},
        doc_size=len(body),
    )
    db.add(doc)
    db.flush()
    key = storage.storage_key(
        tenant_id=tenant.tenant_id,
        document_id=doc.doc_id,
        version=str(version),
        filename=filename,
    )
    storage.write_bytes(key, body)
    db.add(
        DocumentFile(
            tenant_id=tenant.tenant_id,
            doc_id=doc.doc_id,
            version=version,
            storage_key=key,
            filename=filename,
            content_type="text/plain",
            size_bytes=len(body),
        )
    )
    job = IndexJob(
        tenant_id=tenant.tenant_id,
        doc_id=doc.doc_id,
        version=version,
        status="pending",
    )
    db.add(job)
    db.commit()
    return doc, job


@pytest.mark.integration
def test_f04_t01_publish_index_sections_and_leaves(db: Session, tmp_path) -> None:
    tenant, user = _seed_tenant(db)
    storage = StorageService(root=tmp_path)
    md = "# 政策\n\n## 时效\n\n退货窗口 30 天内申请。\n"
    doc, job = _published_doc_with_file(
        db, storage, tenant=tenant, user=user, body=b"ignored"
    )
    parser = ScriptedDocumentParser(default=md)
    emb = HashingEmbedder()
    process_index_job(db, job.id, embedder=emb, storage=storage, parser=parser)
    db.refresh(job)
    assert job.status == "succeeded"

    sec = db.execute(
        text(
            "SELECT count(*) FROM rag_service.document_sections "
            "WHERE doc_id = CAST(:id AS uuid) AND is_latest "
            "AND path <> '' AND content <> ''"
        ),
        {"id": str(doc.doc_id)},
    ).scalar()
    assert int(sec or 0) >= 1
    chunks = db.execute(
        text(
            "SELECT count(*) FROM rag_service.document_chunks "
            "WHERE doc_id = CAST(:id AS uuid) AND is_latest"
        ),
        {"id": str(doc.doc_id)},
    ).scalar()
    assert int(chunks or 0) >= 1


@pytest.mark.integration
def test_f04_t02_review_not_indexed(db: Session, tmp_path) -> None:
    tenant, user = _seed_tenant(db)
    storage = StorageService(root=tmp_path)
    doc, job = _published_doc_with_file(db, storage, tenant=tenant, user=user)
    doc.publish_status = "review"
    db.commit()
    process_index_job(
        db,
        job.id,
        embedder=HashingEmbedder(),
        storage=storage,
        parser=ScriptedDocumentParser(default="# A\n\nbody"),
    )
    latest = db.execute(
        text(
            "SELECT count(*) FROM rag_service.document_chunks "
            "WHERE doc_id = CAST(:id AS uuid) AND is_latest"
        ),
        {"id": str(doc.doc_id)},
    ).scalar()
    assert int(latest or 0) == 0


@pytest.mark.integration
def test_f04_t03_cross_tenant_search(db: Session, tmp_path) -> None:
    storage = StorageService(root=tmp_path)
    emb = HashingEmbedder()
    parser = ScriptedDocumentParser(default="# A\n\nUNIQUE_TENANT_A_PHRASE\n")

    ta, ua = _seed_tenant(db)
    doc_a, job_a = _published_doc_with_file(db, storage, tenant=ta, user=ua)
    process_index_job(
        db, job_a.id, embedder=emb, storage=storage, parser=parser
    )

    tb, _ub = _seed_tenant(db)

    def factory():
        return db

    searcher = PgKnowledgeSearcher(factory, embedder=emb)
    hits_b = searcher.search(tb.tenant_id, "UNIQUE_TENANT_A_PHRASE", top_k=5)
    assert hits_b == []
    hits_a = searcher.search(ta.tenant_id, "UNIQUE_TENANT_A_PHRASE", top_k=5)
    assert hits_a
    assert any("UNIQUE_TENANT_A_PHRASE" in h.content for h in hits_a)


@pytest.mark.integration
def test_f04_t04_empty_txt(db: Session, tmp_path) -> None:
    tenant, user = _seed_tenant(db)
    storage = StorageService(root=tmp_path)
    doc, job = _published_doc_with_file(
        db, storage, tenant=tenant, user=user, body=b""
    )
    process_index_job(
        db,
        job.id,
        embedder=HashingEmbedder(),
        storage=storage,
        parser=ScriptedDocumentParser(default=""),
    )
    db.refresh(job)
    assert job.status == "succeeded"
    n = db.execute(
        text(
            "SELECT count(*) FROM rag_service.document_sections "
            "WHERE doc_id = CAST(:id AS uuid)"
        ),
        {"id": str(doc.doc_id)},
    ).scalar()
    assert int(n or 0) == 0


@pytest.mark.integration
def test_f04_t05_version_supersede(db: Session, tmp_path) -> None:
    tenant, user = _seed_tenant(db)
    storage = StorageService(root=tmp_path)
    emb = HashingEmbedder()
    group_id = uuid4()
    doc_v1, job1 = _published_doc_with_file(
        db,
        storage,
        tenant=tenant,
        user=user,
        version=1,
        doc_group_id=group_id,
        is_latest=True,
    )
    process_index_job(
        db,
        job1.id,
        embedder=emb,
        storage=storage,
        parser=ScriptedDocumentParser(default="# V1\n\nOLD_VERSION_PHRASE\n"),
    )
    db.refresh(doc_v1)
    assert doc_v1.index_status == "ready"
    assert doc_v1.is_latest is True

    # App maintains single is_latest per group (no DB partial unique).
    doc_v1.is_latest = False
    db.commit()

    doc_v2, job2 = _published_doc_with_file(
        db,
        storage,
        tenant=tenant,
        user=user,
        version=2,
        doc_group_id=group_id,
        is_latest=True,
    )

    process_index_job(
        db,
        job2.id,
        embedder=emb,
        storage=storage,
        parser=ScriptedDocumentParser(default="# V2\n\nNEW_VERSION_PHRASE\n"),
    )
    db.refresh(doc_v1)
    db.refresh(doc_v2)
    assert doc_v2.is_latest is True
    assert doc_v1.is_latest is False

    def factory():
        return db

    old_latest = db.execute(
        text(
            """
            SELECT count(*) FROM rag_service.document_sections
            WHERE doc_id = CAST(:id AS uuid)
              AND is_latest = true
            """
        ),
        {"id": str(doc_v1.doc_id)},
    ).scalar()
    assert int(old_latest or 0) == 0

    searcher = PgKnowledgeSearcher(factory, embedder=emb)
    hits_old = searcher.search(tenant.tenant_id, "OLD_VERSION_PHRASE", top_k=5)
    hits_new = searcher.search(tenant.tenant_id, "NEW_VERSION_PHRASE", top_k=5)
    # F04-T05: non-latest v1 must not surface; hashing embedder may false-match new text.
    assert not any("OLD_VERSION_PHRASE" in h.content for h in hits_old)
    assert hits_new
    assert any("NEW_VERSION_PHRASE" in h.content for h in hits_new)


@pytest.mark.integration
def test_f04_t06_soft_delete(db: Session, tmp_path) -> None:
    from datetime import datetime, timezone

    from rag_api.indexing.worker import deactivate_document_index

    tenant, user = _seed_tenant(db)
    storage = StorageService(root=tmp_path)
    emb = HashingEmbedder()
    doc, job = _published_doc_with_file(db, storage, tenant=tenant, user=user)
    process_index_job(
        db,
        job.id,
        embedder=emb,
        storage=storage,
        parser=ScriptedDocumentParser(default="# A\n\nSOFT_DELETE_PHRASE\n"),
    )
    doc.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    deactivate_document_index(db, tenant_id=tenant.tenant_id, document_id=doc.doc_id)
    db.commit()

    def factory():
        return db

    hits = PgKnowledgeSearcher(factory, embedder=emb).search(
        tenant.tenant_id, "SOFT_DELETE_PHRASE", top_k=5
    )
    assert hits == []


@pytest.mark.integration
def test_f04_t07_parse_failure(db: Session, tmp_path) -> None:
    tenant, user = _seed_tenant(db)
    storage = StorageService(root=tmp_path)
    doc, job = _published_doc_with_file(db, storage, tenant=tenant, user=user)
    with pytest.raises(Exception):
        process_index_job(
            db,
            job.id,
            embedder=HashingEmbedder(),
            storage=storage,
            parser=ScriptedDocumentParser(fail_suffixes=frozenset({".txt"})),
        )
    db.refresh(job)
    db.refresh(doc)
    assert job.status == "failed"
    assert doc.index_status == "failed"
    assert doc.error_message
    latest = db.execute(
        text(
            "SELECT count(*) FROM rag_service.document_chunks "
            "WHERE doc_id = CAST(:id AS uuid) AND is_latest"
        ),
        {"id": str(doc.doc_id)},
    ).scalar()
    assert int(latest or 0) == 0


@pytest.mark.integration
def test_f04_t08_search_returns_section_and_path(db: Session, tmp_path) -> None:
    tenant, user = _seed_tenant(db)
    storage = StorageService(root=tmp_path)
    emb = HashingEmbedder()
    _, job = _published_doc_with_file(db, storage, tenant=tenant, user=user)
    process_index_job(
        db,
        job.id,
        embedder=emb,
        storage=storage,
        parser=ScriptedDocumentParser(
            default="# 政策\n\n## 时效\n\n独特短语退货三十天窗口\n"
        ),
    )

    def factory():
        return db

    hits = PgKnowledgeSearcher(factory, embedder=emb).search(
        tenant.tenant_id, "独特短语退货三十天窗口", top_k=3
    )
    assert hits
    assert hits[0].path
    assert "独特短语退货三十天窗口" in hits[0].content
    assert hits[0].section_id


@pytest.mark.integration
def test_f04_t09_empty_pdf_succeeds(db: Session, tmp_path) -> None:
    tenant, user = _seed_tenant(db)
    storage = StorageService(root=tmp_path)
    doc, job = _published_doc_with_file(
        db,
        storage,
        tenant=tenant,
        user=user,
        filename="scan.pdf",
        body=b"%PDF-empty",
    )
    process_index_job(
        db,
        job.id,
        embedder=HashingEmbedder(),
        storage=storage,
        parser=ScriptedDocumentParser(empty_suffixes=frozenset({".pdf"})),
    )
    db.refresh(job)
    assert job.status == "succeeded"
    n = db.execute(
        text(
            "SELECT count(*) FROM rag_service.document_sections "
            "WHERE doc_id = CAST(:id AS uuid)"
        ),
        {"id": str(doc.doc_id)},
    ).scalar()
    assert int(n or 0) == 0


@pytest.mark.integration
def test_f04_t10_t11_t12_hierarchy_search(db: Session, tmp_path) -> None:
    tenant, user = _seed_tenant(db)
    storage = StorageService(root=tmp_path)
    emb = HashingEmbedder()
    md = """# 手册

## 章节甲

PHRASE_ONLY_IN_A 内容甲

## 章节乙

PHRASE_ONLY_IN_B 内容乙
"""
    _, job = _published_doc_with_file(db, storage, tenant=tenant, user=user)
    process_index_job(
        db,
        job.id,
        embedder=emb,
        storage=storage,
        parser=ScriptedDocumentParser(default=md),
    )
    secs = db.execute(
        text(
            "SELECT path, content FROM rag_service.document_sections "
            "WHERE tenant_id = CAST(:tid AS uuid) AND is_latest "
            "ORDER BY section_index"
        ),
        {"tid": str(tenant.tenant_id)},
    ).mappings().all()
    paths = [r["path"] for r in secs]
    assert any("章节甲" in p for p in paths)
    assert any("章节乙" in p for p in paths)
    by_path = {r["path"]: r["content"] for r in secs}
    for p, c in by_path.items():
        if "章节甲" in p:
            assert "PHRASE_ONLY_IN_A" in c
            assert "PHRASE_ONLY_IN_B" not in c

    def factory():
        return db

    searcher = PgKnowledgeSearcher(factory, embedder=emb)
    hits = searcher.search(tenant.tenant_id, "PHRASE_ONLY_IN_B", top_k=5)
    assert hits
    assert "PHRASE_ONLY_IN_B" in hits[0].content
    assert "PHRASE_ONLY_IN_A" not in hits[0].content
    assert "章节乙" in hits[0].path

    # T12: same section should appear once even if we ask for more
    hits2 = searcher.search(tenant.tenant_id, "PHRASE_ONLY_IN_B", top_k=10)
    section_ids = [h.section_id for h in hits2]
    assert len(section_ids) == len(set(section_ids))
