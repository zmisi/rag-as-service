#!/usr/bin/env python3
"""Rebuild document rows from local storage when DB rows were wiped.

Skips tiny test fixtures named note.txt. Keeps existing file_storage_path paths.
Creates published docs + pending ingest jobs (optional sync ingest).
Each document version uses a single source file (first file in the version dir).

Usage (repo root or apps/api):
  DATABASE_URL=postgresql+psycopg://... \\
    python scripts/restore_docs_from_storage.py [--index]
"""

from __future__ import annotations

import mimetypes
import sys
from collections import defaultdict
from pathlib import Path
from uuid import UUID

API_SRC = Path(__file__).resolve().parents[1] / "apps" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from rag_api.config import get_settings
from rag_api.db.models import Document, IngestJob, Tenant, TenantMember
from rag_api.domain.documents.constants import content_sha256
from rag_api.ingestion.worker import process_ingest_job


def _guess_tag(filename: str) -> str:
    lower = filename.lower()
    if "faq" in lower:
        return "faq"
    if "章程" in filename or "charter" in lower or "plan" in lower or "招生" in filename:
        return "knowledge_base"
    return "knowledge_base"


def _title_from_filename(filename: str) -> str:
    stem = Path(filename).stem.strip()
    return stem or filename


def restore(*, do_index: bool) -> None:
    settings = get_settings()
    engine = create_engine(
        settings.database_url,
        connect_args={"options": "-csearch_path=rag_service,public"},
    )
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    root: Path = settings.storage_root
    if not root.is_dir():
        raise SystemExit(f"storage root missing: {root}")

    groups: dict[tuple[UUID, UUID], list[tuple[str, Path]]] = defaultdict(list)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name == "note.txt" and path.stat().st_size <= 64:
            continue
        try:
            rel = path.relative_to(root)
            tenant_s, doc_s, version_s, filename = rel.parts[:4]
            if filename != path.name:
                continue
            tenant_id = UUID(tenant_s)
            doc_id = UUID(doc_s)
        except (ValueError, IndexError):
            continue
        groups[(tenant_id, doc_id)].append((version_s, path))

    restored = 0
    with SessionLocal() as db:
        for (tenant_id, doc_id), files in sorted(groups.items()):
            tenant = db.get(Tenant, tenant_id)
            if tenant is None:
                print(f"skip missing tenant {tenant_id}")
                continue
            owner = db.scalar(
                select(TenantMember.user_id).where(TenantMember.tenant_id == tenant_id).limit(1)
            )
            if owner is None:
                print(f"skip tenant {tenant.tenant_name}: no member")
                continue

            existing = db.get(Document, doc_id)
            if existing is not None and existing.deleted_at is None:
                print(f"keep existing doc {doc_id} ({existing.doc_name})")
                continue

            files_sorted = sorted(files, key=lambda item: item[0])
            version_dir = files_sorted[-1][0]
            version_files = [p for v, p in files_sorted if v == version_dir]
            try:
                version_number = int(float(version_dir)) if version_dir else 1
            except ValueError:
                version_number = 1
            if version_number < 1:
                version_number = 1

            primary = sorted(version_files, key=lambda p: p.name)[0]
            title = _title_from_filename(primary.name)
            tag = _guess_tag(primary.name)
            blob = primary.read_bytes()
            digest = content_sha256(blob)
            ctype = mimetypes.guess_type(primary.name)[0] or "application/octet-stream"
            storage_path = str(primary.relative_to(root))

            doc = Document(
                doc_id=doc_id,
                tenant_id=tenant_id,
                created_by=owner,
                doc_group_id=doc_id,
                doc_name=title,
                doc_tag=tag,
                publish_status="published",
                ingest_status="pending",
                version_number=version_number,
                is_latest=True,
                file_content_sha256=digest,
                file_storage_path=storage_path,
                file_name=primary.name,
                file_content_type=ctype,
                file_type=primary.suffix.lstrip(".") or None,
                file_size_bytes=primary.stat().st_size,
                file_metadata={},
            )
            db.add(doc)
            db.flush()

            job = IngestJob(
                tenant_id=tenant_id,
                doc_id=doc_id,
                version=version_number,
                status="pending",
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            restored += 1
            print(
                f"restored {tenant.tenant_name}/{doc_id} "
                f"title={title!r} file={primary.name} job={job.id}"
            )

            if do_index:
                try:
                    process_ingest_job(db, job.id)
                    db.refresh(doc)
                    print(f"  indexed status={doc.ingest_status}")
                except Exception as exc:  # noqa: BLE001
                    print(f"  index failed: {exc}")

    print(f"done restored={restored}")


if __name__ == "__main__":
    restore(do_index="--index" in sys.argv)
