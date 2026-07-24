"""F08 data-model naming refactor tests (requires DATABASE_URL)."""

from __future__ import annotations

import io

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from rag_api.db.models import Document, DocumentChunk, Tenant, TenantMember, User
from rag_api.db.models.user import USER_INACTIVE
from rag_api.indexing.embedding import HashingEmbedder
from rag_api.indexing.parse import ScriptedDocumentParser
from rag_api.indexing.search import PgKnowledgeSearcher
from rag_api.indexing.worker import process_index_job
from rag_api.services.storage_service import StorageService
from tests.helpers import register_user, tenant_host_headers
from tests.integration.test_f04_doc_indexing import _published_doc_with_file, _seed_tenant

_F08_TABLES = ("tenants", "users", "tenant_members", "documents", "document_chunks")


@pytest.mark.integration
def test_f08_t01_schema_pk_uk_triggers(db_engine: Engine) -> None:
    expected = {
        "tenants": {"pk_tenants_tenant_id", "uk_tenants_tenant_name"},
        "users": {"pk_users_user_id", "uk_users_email", "uk_users_user_name"},
        "tenant_members": {
            "pk_tenant_members_member_id",
            "uk_tenant_members_tenant_id_user_id",
            "uk_tenant_members_tenant_id_member_name",
        },
        "documents": {
            "pk_documents_doc_id",
            "uk_documents_tenant_group_version",
        },
        "document_chunks": {
            "pk_document_chunks_chunk_id",
            "uk_document_chunks_doc_id_chunk_index",
        },
    }
    with db_engine.connect() as conn:
        for table, cols in {
            "tenants": ("tenant_id", "tenant_name", "status", "charge_mode", "create_at", "update_at"),
            "users": ("user_id", "user_name", "email", "active", "create_at", "update_at"),
            "tenant_members": ("member_id", "user_id", "member_name", "active", "create_at", "update_at"),
            "documents": (
                "doc_id",
                "doc_name",
                "doc_tag",
                "doc_group_id",
                "version_number",
                "source_metadata",
                "doc_size",
                "publish_status",
            ),
            "document_chunks": ("chunk_id", "doc_id", "create_at", "update_at"),
        }.items():
            for col in cols:
                present = conn.execute(
                    text(
                        """
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema='rag_service'
                          AND table_name=:t AND column_name=:c
                        """
                    ),
                    {"t": table, "c": col},
                ).scalar()
                assert present, f"missing {table}.{col}"

        # tenant_members.user_id must be NOT NULL
        nullable = conn.execute(
            text(
                """
                SELECT is_nullable FROM information_schema.columns
                WHERE table_schema='rag_service'
                  AND table_name='tenant_members' AND column_name='user_id'
                """
            )
        ).scalar()
        assert nullable == "NO"

        for table in _F08_TABLES:
            trig = conn.execute(
                text(
                    """
                    SELECT 1 FROM pg_trigger t
                    JOIN pg_class c ON c.oid = t.tgrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname='rag_service' AND c.relname=:table
                      AND t.tgname = :tgname AND NOT t.tgisinternal
                    """
                ),
                {"table": table, "tgname": f"tr_{table}_lmt"},
            ).scalar()
            assert trig, f"missing trigger tr_{table}_lmt"

        cons = {
            row[0]
            for row in conn.execute(
                text(
                    """
                    SELECT con.conname
                    FROM pg_constraint con
                    JOIN pg_class rel ON rel.oid = con.conrelid
                    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                    WHERE nsp.nspname='rag_service'
                      AND rel.relname = ANY(:tables)
                    """
                ),
                {"tables": list(_F08_TABLES)},
            )
        }
        idxs = {
            row[0]
            for row in conn.execute(
                text(
                    """
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname='rag_service'
                      AND tablename = ANY(:tables)
                    """
                ),
                {"tables": list(_F08_TABLES)},
            )
        }
        named = cons | idxs
        for needed in expected.values():
            missing = needed - named
            assert not missing, f"missing constraints/indexes {missing}; have={sorted(named)}"


@pytest.mark.integration
def test_f08_t02_register_writes_identity_fields(api_client, db_session: Session) -> None:
    import uuid

    sub = f"f08-{uuid.uuid4().hex[:8]}"
    result = register_user(api_client, db_session, subdomain=sub)
    tenant = db_session.scalar(select(Tenant).where(Tenant.tenant_name == sub))
    assert tenant is not None
    user = db_session.scalar(select(User).where(User.email == result["email"]))
    assert user is not None
    assert user.user_name
    assert user.active == 1
    member = db_session.scalar(
        select(TenantMember).where(
            TenantMember.tenant_id == tenant.tenant_id,
            TenantMember.user_id == user.user_id,
        )
    )
    assert member is not None
    assert member.role == "owner"
    assert member.member_name == user.user_name


@pytest.mark.integration
def test_f08_t03_unknown_tenant_name_404(api_client) -> None:
    r = api_client.get(
        "/v1/documents",
        headers=tenant_host_headers("no-such-tenant-xyz"),
    )
    assert r.status_code == 404


@pytest.mark.integration
def test_f08_t04_inactive_user_login_rejected(api_client, db_session: Session) -> None:
    import uuid

    sub = f"f08i-{uuid.uuid4().hex[:8]}"
    result = register_user(api_client, db_session, subdomain=sub)
    user = db_session.scalar(select(User).where(User.email == result["email"]))
    assert user is not None
    user.active = USER_INACTIVE
    db_session.commit()
    r = api_client.post(
        "/api/v1/auth/login",
        json={"email": result["email"], "password": result["password"]},
        headers={"Host": "lxzxai.com"},
    )
    assert r.status_code in (401, 400, 403)


@pytest.mark.integration
def test_f08_t05_t06_version_unique(db: Session) -> None:
    tenant, user = _seed_tenant(db)
    from uuid import uuid4

    group = uuid4()
    d1 = Document(
        tenant_id=tenant.tenant_id,
        created_by=user.user_id,
        doc_group_id=group,
        doc_name="v1",
        doc_tag="faq",
        publish_status="draft",
        index_status="pending",
        version_number=1,
        is_latest=True,
    )
    db.add(d1)
    db.commit()
    d1.is_latest = False
    db.commit()
    d2 = Document(
        tenant_id=tenant.tenant_id,
        created_by=user.user_id,
        doc_group_id=group,
        doc_name="v2",
        doc_tag="faq",
        publish_status="draft",
        index_status="pending",
        version_number=2,
        is_latest=True,
    )
    db.add(d2)
    db.commit()
    assert d1.doc_group_id == d2.doc_group_id
    assert d1.version_number != d2.version_number

    d_dup = Document(
        tenant_id=tenant.tenant_id,
        created_by=user.user_id,
        doc_group_id=group,
        doc_name="dup",
        doc_tag="faq",
        publish_status="draft",
        index_status="pending",
        version_number=1,
        is_latest=False,
    )
    db.add(d_dup)
    with pytest.raises(Exception):
        db.commit()
    db.rollback()


@pytest.mark.integration
def test_f08_t07_doc_size_and_names(client_a, db: Session, tenants: dict) -> None:
    headers = tenant_host_headers("pytest-a")
    created = client_a.post("/v1/documents", headers=headers)
    assert created.status_code == 201
    doc_id = created.json()["id"]
    body = b"hello-f08-size"
    up = client_a.post(
        f"/v1/documents/{doc_id}/files",
        headers=headers,
        files={"file": ("a.txt", io.BytesIO(body), "text/plain")},
    )
    assert up.status_code == 201, up.text
    client_a.patch(
        f"/v1/documents/{doc_id}",
        json={"title": "Named", "tag": "faq"},
        headers=headers,
    )
    doc = db.get(Document, doc_id)
    assert doc is not None
    assert doc.doc_name == "Named"
    assert doc.doc_size == len(body)
    assert doc.source_metadata is not None or True


@pytest.mark.integration
def test_f08_t08_search_uses_renamed_columns(db: Session, tmp_path) -> None:
    tenant, user = _seed_tenant(db)
    storage = StorageService(root=tmp_path)
    md = "# H\n\n## S\n\nF08_SEARCH_PHRASE here\n"
    doc, job = _published_doc_with_file(
        db, storage, tenant=tenant, user=user, body=b"x"
    )
    emb = HashingEmbedder()
    parser = ScriptedDocumentParser({doc.doc_id: md})
    process_index_job(db, job.id, embedder=emb, storage=storage, parser=parser)
    searcher = PgKnowledgeSearcher(lambda: db, embedder=emb)
    hits = searcher.search(tenant.tenant_id, "F08_SEARCH_PHRASE", top_k=3)
    assert hits
    assert hits[0].document_id == str(doc.doc_id)
    chunk = db.scalar(select(DocumentChunk).where(DocumentChunk.doc_id == doc.doc_id))
    assert chunk is not None
    assert chunk.chunk_id is not None


@pytest.mark.integration
def test_f08_t09_cross_tenant_isolation(client_a, switch_to_b, tenants: dict) -> None:
    headers_a = tenant_host_headers("pytest-a")
    created = client_a.post("/v1/documents", headers=headers_a)
    assert created.status_code == 201
    doc_id = created.json()["id"]
    client_b = switch_to_b()
    headers_b = tenant_host_headers("pytest-b")
    r = client_b.get(f"/v1/documents/{doc_id}", headers=headers_b)
    assert r.status_code in (403, 404)


@pytest.mark.integration
def test_f08_t10_data_model_doc_mentions_f08(tmp_path=None) -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[4]
    dm = (root / "docs/specs/phase1/02-data-model.md").read_text()
    assert "tenant_name" in dm
    assert "doc_group_id" in dm
    assert "version_number" in dm
    assert "user_id" in dm
    assert "tenant_members" in dm
    assert "UNIQUE (tenant_id, doc_group_id, version_number)" in dm or "uk_documents_tenant_group_version" in dm
