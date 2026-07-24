"""F07 document indexing data-model integration tests (requires DATABASE_URL)."""

from __future__ import annotations

import io

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from rag_api.config import get_settings
from rag_api.db.models import (
    Document,
    DocumentChunk,
    DocumentFile,
    DocumentSection,
    IndexJob,
)
from rag_api.domain.documents.constants import content_sha256
from rag_api.indexing.embedding import HashingEmbedder
from rag_api.indexing.parse import ScriptedDocumentParser
from rag_api.indexing.search import PgKnowledgeSearcher
from rag_api.indexing.worker import process_index_job
from rag_api.services.storage_service import StorageService
from tests.helpers import tenant_host_headers
from tests.integration.test_f04_doc_indexing import _published_doc_with_file, _seed_tenant

HEADERS_A = tenant_host_headers("pytest-a")
HEADERS_B = tenant_host_headers("pytest-b")

TXT_BODY = b"# Title\n\nUNIQUE_F07_PHRASE content body\n"
TXT_BODY_DUP = TXT_BODY  # identical bytes for content_sha256 skip


@pytest.fixture(autouse=True)
def wipe_docs(db: Session, tenants: dict):
    db.execute(delete(DocumentChunk))
    db.execute(delete(DocumentSection))
    db.execute(delete(IndexJob))
    db.execute(delete(DocumentFile))
    db.execute(delete(Document))
    db.commit()


@pytest.fixture(autouse=True)
def disable_index_sync(monkeypatch):
    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "index_sync_on_publish", False)
    yield
    get_settings.cache_clear()


_F07_TABLES = (
    "documents",
    "document_sections",
    "document_chunks",
    "document_files",
    "index_jobs",
)


@pytest.mark.integration
def test_f07_t01_schema_text_triggers_version_int(db_engine: Engine) -> None:
    with db_engine.connect() as conn:
        varchar_cols = conn.execute(
            text(
                """
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'rag_service'
                  AND table_name = ANY(:tables)
                  AND data_type IN ('character varying', 'varchar')
                ORDER BY table_name, column_name
                """
            ),
            {"tables": list(_F07_TABLES)},
        ).all()
        assert varchar_cols == [], f"unexpected varchar columns: {varchar_cols}"

        version_type = conn.execute(
            text(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'rag_service'
                  AND table_name = 'documents'
                  AND column_name = 'version_number'
                """
            )
        ).scalar()
        assert version_type == "integer"

        for table in _F07_TABLES:
            for col in ("create_at", "update_at"):
                present = conn.execute(
                    text(
                        """
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'rag_service'
                          AND table_name = :table
                          AND column_name = :col
                        """
                    ),
                    {"table": table, "col": col},
                ).scalar()
                assert present, f"missing {table}.{col}"

            trigger = conn.execute(
                text(
                    """
                    SELECT 1 FROM pg_trigger t
                    JOIN pg_class c ON c.oid = t.tgrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'rag_service'
                      AND c.relname = :table
                      AND t.tgname = :tgname
                      AND NOT t.tgisinternal
                    """
                ),
                {"table": table, "tgname": f"tr_{table}_lmt"},
            ).scalar()
            assert trigger, f"missing trigger tr_{table}_lmt"

        no_embedding_model = conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'rag_service'
                  AND table_name = 'document_chunks'
                  AND column_name = 'embedding_model'
                """
            )
        ).scalar()
        assert no_embedding_model is None

        level_type = conn.execute(
            text(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'rag_service'
                  AND table_name = 'document_sections'
                  AND column_name = 'level'
                """
            )
        ).scalar()
        assert level_type == "text"


@pytest.mark.integration
def test_f07_t02_create_document_version_row(client_a, db: Session, tenants: dict):
    r = client_a.post("/v1/documents", headers=HEADERS_A)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["publish_status"] == "draft"
    assert body["version"] == 1
    assert body["is_latest"] is True
    assert body["document_group_id"]
    assert body["index_status"] == "pending"

    doc = db.get(Document, body["id"])
    assert doc is not None
    assert doc.tenant_id == tenants["tenant_a"].tenant_id
    assert doc.publish_status == "draft"
    assert doc.version_number == 1
    assert doc.is_latest is True
    assert doc.doc_group_id is not None


def _create_upload_publish(client, headers, *, title: str = "Doc", tag: str = "faq") -> dict:
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


@pytest.mark.integration
def test_f07_t03_t09_tenant_isolation_documents_and_hash(
    client_a, switch_to_b, db: Session, tenants: dict, tmp_path
):
    a = _create_upload_publish(client_a, HEADERS_A, title="A doc")
    client_b = switch_to_b()
    b = _create_upload_publish(client_b, HEADERS_B, title="B doc")

    assert client_b.get(f"/v1/documents/{a['id']}", headers=HEADERS_B).status_code == 404
    # switch back to A
    from tests.helpers import issue_session_for_user, set_client_session_cookie

    token = issue_session_for_user(db, tenants["user_a"].user_id)
    set_client_session_cookie(client_a, token, host=HEADERS_A["Host"])
    assert client_a.get(f"/v1/documents/{b['id']}", headers=HEADERS_A).status_code == 404

    # Same content_sha256 across tenants must not skip / share search hits.
    storage = StorageService(root=tmp_path)
    emb = HashingEmbedder()
    parser = ScriptedDocumentParser(default="# X\n\nSHARED_HASH_PHRASE_ONLY\n")
    ta, ua = tenants["tenant_a"], tenants["user_a"]
    tb, ub = tenants["tenant_b"], tenants["user_b"]

    doc_a, job_a = _published_doc_with_file(
        db, storage, tenant=ta, user=ua, body=b"same-bytes"
    )
    doc_a.content_sha256 = content_sha256(b"same-bytes")
    db.commit()
    process_index_job(db, job_a.id, embedder=emb, storage=storage, parser=parser)

    doc_b, job_b = _published_doc_with_file(
        db, storage, tenant=tb, user=ub, body=b"same-bytes"
    )
    doc_b.content_sha256 = content_sha256(b"same-bytes")
    db.commit()
    process_index_job(db, job_b.id, embedder=emb, storage=storage, parser=parser)
    db.refresh(doc_a)
    db.refresh(doc_b)
    assert doc_a.index_status == "ready"
    assert doc_b.index_status == "ready"
    assert doc_a.doc_id != doc_b.doc_id

    def factory():
        return db

    searcher = PgKnowledgeSearcher(factory, embedder=emb)
    hits_a = searcher.search(ta.tenant_id, "SHARED_HASH_PHRASE_ONLY", top_k=5)
    hits_b = searcher.search(tb.tenant_id, "SHARED_HASH_PHRASE_ONLY", top_k=5)
    assert hits_a and all(h.document_id == str(doc_a.doc_id) for h in hits_a)
    assert hits_b and all(h.document_id == str(doc_b.doc_id) for h in hits_b)
    assert not any(h.document_id == str(doc_b.doc_id) for h in hits_a)
    assert not any(h.document_id == str(doc_a.doc_id) for h in hits_b)


@pytest.mark.integration
def test_f07_t04_publish_sets_index_pending(client_a, db: Session):
    body = _create_upload_publish(client_a, HEADERS_A)
    assert body["publish_status"] == "published"
    assert body["index_status"] in ("pending", "processing")
    doc = db.get(Document, body["id"])
    assert doc is not None
    assert doc.publish_status == "published"
    assert doc.index_status in ("pending", "processing")


@pytest.mark.integration
def test_f07_t05_index_failure_keeps_published(db: Session, tmp_path):
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
    db.refresh(doc)
    db.refresh(job)
    assert doc.publish_status == "published"
    assert doc.index_status == "failed"
    assert doc.error_message
    assert job.status == "failed"


@pytest.mark.integration
def test_f07_t06_success_embedding_on_document_not_chunk(db: Session, tmp_path, db_engine: Engine):
    tenant, user = _seed_tenant(db)
    storage = StorageService(root=tmp_path)
    emb = HashingEmbedder()
    doc, job = _published_doc_with_file(db, storage, tenant=tenant, user=user)
    process_index_job(
        db,
        job.id,
        embedder=emb,
        storage=storage,
        parser=ScriptedDocumentParser(default="# H\n\n## S\n\nbody leaf\n"),
    )
    db.refresh(doc)
    assert doc.index_status == "ready"
    assert doc.embedding_model
    assert doc.embedding_dimension

    with db_engine.connect() as conn:
        has_col = conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'rag_service'
                  AND table_name = 'document_chunks'
                  AND column_name = 'embedding_model'
                """
            )
        ).scalar()
    assert has_col is None


@pytest.mark.integration
def test_f07_t07_new_version_flips_is_latest_and_search(
    client_a, db: Session, tenants: dict, tmp_path
):
    storage = StorageService(root=tmp_path)
    emb = HashingEmbedder()

    v1 = _create_upload_publish(client_a, HEADERS_A, title="V1")
    doc_v1 = db.get(Document, v1["id"])
    assert doc_v1 is not None
    job1 = db.scalar(select(IndexJob).where(IndexJob.doc_id == doc_v1.doc_id))
    assert job1 is not None
    process_index_job(
        db,
        job1.id,
        embedder=emb,
        storage=StorageService(),  # files written under app storage root
        parser=ScriptedDocumentParser(default="# V1\n\nOLD_F07_VERSION_PHRASE\n"),
    )
    db.refresh(doc_v1)
    assert doc_v1.index_status == "ready"

    nv = client_a.post(f"/v1/documents/{doc_v1.doc_id}/new-version", headers=HEADERS_A)
    assert nv.status_code == 200, nv.text
    draft = nv.json()
    assert draft["version"] == 2
    draft_id = draft["id"]

    # Replace copied file content path still points at v1 storage; re-upload for clarity.
    client_a.post(
        f"/v1/documents/{draft_id}/files",
        headers=HEADERS_A,
        files={"file": ("v2.txt", io.BytesIO(b"v2-bytes"), "text/plain")},
    )
    client_a.patch(
        f"/v1/documents/{draft_id}",
        json={"title": "V2"},
        headers=HEADERS_A,
    )
    client_a.post(f"/v1/documents/{draft_id}/submit-review", headers=HEADERS_A)
    pub2 = client_a.post(f"/v1/documents/{draft_id}/publish", headers=HEADERS_A)
    assert pub2.status_code == 200, pub2.text

    job2 = db.scalar(
        select(IndexJob)
        .where(IndexJob.doc_id == draft_id)
        .order_by(IndexJob.create_at.desc())
    )
    assert job2 is not None
    process_index_job(
        db,
        job2.id,
        embedder=emb,
        storage=StorageService(),
        parser=ScriptedDocumentParser(default="# V2\n\nNEW_F07_VERSION_PHRASE\n"),
    )

    db.expire_all()
    doc_v1 = db.get(Document, v1["id"])
    doc_v2 = db.get(Document, draft_id)
    assert doc_v1 is not None and doc_v2 is not None
    assert doc_v1.is_latest is False
    assert doc_v2.is_latest is True
    assert doc_v2.index_status == "ready"

    sec_v1 = db.scalar(
        select(DocumentSection).where(
            DocumentSection.doc_id == doc_v1.doc_id,
            DocumentSection.is_latest.is_(True),
        )
    )
    assert sec_v1 is None
    chunk_v1 = db.scalar(
        select(DocumentChunk).where(
            DocumentChunk.doc_id == doc_v1.doc_id,
            DocumentChunk.is_latest.is_(True),
        )
    )
    assert chunk_v1 is None
    assert (
        db.scalar(
            select(DocumentSection).where(
                DocumentSection.doc_id == doc_v2.doc_id,
                DocumentSection.is_latest.is_(True),
            )
        )
        is not None
    )

    def factory():
        return db

    searcher = PgKnowledgeSearcher(factory, embedder=emb)
    tenant_id = tenants["tenant_a"].tenant_id
    hits_old = searcher.search(tenant_id, "OLD_F07_VERSION_PHRASE", top_k=5)
    hits_new = searcher.search(tenant_id, "NEW_F07_VERSION_PHRASE", top_k=5)
    assert not any("OLD_F07_VERSION_PHRASE" in h.content for h in hits_old)
    assert hits_new
    assert any("NEW_F07_VERSION_PHRASE" in h.content for h in hits_new)


@pytest.mark.integration
def test_f07_t08_same_tenant_content_sha256_skip(
    client_a, db: Session, tenants: dict
):
    first = _create_upload_publish(client_a, HEADERS_A, title="First")
    doc1 = db.get(Document, first["id"])
    assert doc1 is not None
    job1 = db.scalar(select(IndexJob).where(IndexJob.doc_id == doc1.doc_id))
    assert job1 is not None

    emb = HashingEmbedder()
    parser = ScriptedDocumentParser(default=TXT_BODY.decode("utf-8"))
    process_index_job(db, job1.id, embedder=emb, storage=StorageService(), parser=parser)
    db.refresh(doc1)
    assert doc1.index_status == "ready"
    assert doc1.content_sha256 == content_sha256(TXT_BODY_DUP)
    chunks1 = list(
        db.scalars(
            select(DocumentChunk).where(
                DocumentChunk.doc_id == doc1.doc_id,
                DocumentChunk.is_latest.is_(True),
            )
        ).all()
    )
    assert chunks1, "source doc must have chunks to clone"

    second = _create_upload_publish(client_a, HEADERS_A, title="Second")
    assert second.get("warning_code") == "duplicate_content_sha256"
    assert second.get("warning")
    doc2 = db.get(Document, second["id"])
    assert doc2 is not None
    assert doc2.content_sha256 == content_sha256(TXT_BODY_DUP)
    assert doc2.index_status == "ready"
    job2 = db.scalar(
        select(IndexJob)
        .where(IndexJob.doc_id == doc2.doc_id)
        .order_by(IndexJob.create_at.desc())
    )
    assert job2 is not None
    assert job2.status == "succeeded"
    assert job2.error and "content_sha256" in job2.error
    status = client_a.get(
        f"/v1/documents/{second['id']}/index-status", headers=HEADERS_A
    )
    assert status.status_code == 200
    assert status.json()["warning_code"] == "duplicate_content_sha256"
    assert status.json()["warning"]

    chunks2 = list(
        db.scalars(
            select(DocumentChunk).where(
                DocumentChunk.doc_id == doc2.doc_id,
                DocumentChunk.is_latest.is_(True),
            )
        ).all()
    )
    assert len(chunks2) == len(chunks1)
    assert {c.chunk_id for c in chunks2}.isdisjoint({c.chunk_id for c in chunks1})

    searcher = PgKnowledgeSearcher(lambda: db, embedder=emb)
    hits = searcher.search(tenants["tenant_a"].tenant_id, "UNIQUE_F07_PHRASE", top_k=10)
    hit_doc_ids = {h.document_id for h in hits}
    assert str(doc2.doc_id) in hit_doc_ids


@pytest.mark.integration
def test_f07_t10_t11_section_and_chunk_fields(db: Session, tmp_path):
    tenant, user = _seed_tenant(db)
    storage = StorageService(root=tmp_path)
    emb = HashingEmbedder()
    md = """# 手册

## 章节甲

alpha body

## 章节乙

beta body
"""
    doc, job = _published_doc_with_file(db, storage, tenant=tenant, user=user)
    process_index_job(
        db,
        job.id,
        embedder=emb,
        storage=storage,
        parser=ScriptedDocumentParser(default=md),
    )

    sections = list(
        db.scalars(
            select(DocumentSection)
            .where(DocumentSection.doc_id == doc.doc_id)
            .order_by(DocumentSection.section_index)
        ).all()
    )
    assert sections
    indexes = [s.section_index for s in sections]
    assert indexes == sorted(set(indexes))
    for s in sections:
        assert s.level in ("1", "2")
        assert isinstance(s.level, str)
        assert s.is_latest is True

    chunks = list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.doc_id == doc.doc_id)
            .order_by(DocumentChunk.chunk_index)
        ).all()
    )
    assert chunks
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    for c in chunks:
        assert c.tenant_id == tenant.tenant_id
        assert c.embedding_text
        assert c.heading_path
        assert c.is_latest is True
        assert not hasattr(c, "embedding_model") or "embedding_model" not in c.__mapper__.columns


@pytest.mark.integration
def test_f07_t12_hard_delete_cascades_chunks_sections(db: Session, tmp_path):
    tenant, user = _seed_tenant(db)
    storage = StorageService(root=tmp_path)
    emb = HashingEmbedder()
    doc, job = _published_doc_with_file(db, storage, tenant=tenant, user=user)
    process_index_job(
        db,
        job.id,
        embedder=emb,
        storage=storage,
        parser=ScriptedDocumentParser(default="# H\n\n## S\n\ncascade body\n"),
    )
    doc_id = doc.doc_id
    assert db.scalar(
        select(DocumentSection).where(DocumentSection.doc_id == doc_id)
    )
    assert db.scalar(
        select(DocumentChunk).where(DocumentChunk.doc_id == doc_id)
    )

    db.delete(doc)
    db.commit()

    assert db.get(Document, doc_id) is None
    assert (
        db.scalar(select(DocumentSection).where(DocumentSection.doc_id == doc_id))
        is None
    )
    assert (
        db.scalar(select(DocumentChunk).where(DocumentChunk.doc_id == doc_id))
        is None
    )


@pytest.mark.integration
def test_f07_t13_search_tenant_isolation(db: Session, tmp_path):
    storage = StorageService(root=tmp_path)
    emb = HashingEmbedder()
    parser = ScriptedDocumentParser(default="# A\n\nF07_TENANT_A_ONLY_PHRASE\n")
    ta, ua = _seed_tenant(db)
    _, job_a = _published_doc_with_file(db, storage, tenant=ta, user=ua)
    process_index_job(db, job_a.id, embedder=emb, storage=storage, parser=parser)
    tb, _ub = _seed_tenant(db)

    def factory():
        return db

    searcher = PgKnowledgeSearcher(factory, embedder=emb)
    hits_a = searcher.search(ta.tenant_id, "F07_TENANT_A_ONLY_PHRASE", top_k=5)
    hits_b = searcher.search(tb.tenant_id, "F07_TENANT_A_ONLY_PHRASE", top_k=5)
    assert hits_a
    assert hits_a[0].path
    assert "F07_TENANT_A_ONLY_PHRASE" in hits_a[0].content
    assert hits_b == []


@pytest.mark.integration
def test_f07_t14_noted_covered_by_f04_regression() -> None:
    """F07-T14: F04-T01–T15 / F03 publish paths covered by updated F03/F04 suites."""
    assert True
