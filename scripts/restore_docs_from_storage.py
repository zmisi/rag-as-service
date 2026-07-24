#!/usr/bin/env python3
"""Rebuild document / document_file rows from local storage when DB rows were wiped.

Skips tiny test fixtures named note.txt. Keeps existing storage_key paths.
Creates published docs + pending index jobs (optional sync index).

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

# Allow running from repo root
API_SRC = Path(__file__).resolve().parents[1] / "apps" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from rag_api.config import get_settings
from rag_api.db.models import Document, DocumentFile, IndexJob, Tenant, TenantMember
from rag_api.domain.documents.constants import content_sha256
from rag_api.indexing.worker import process_index_job


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

    # Group files: (tenant_id, doc_id) -> list[(version_dir, path)]
    groups: dict[tuple[UUID, UUID], list[tuple[str, Path]]] = defaultdict(list)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name == "note.txt" and path.stat().st_size <= 64:
            continue
        # {tenant}/{doc}/{version}/{filename}
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

            # Prefer highest version dir lexicographically (1 > 0.0)
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
            blob = b"".join(p.read_bytes() for p in sorted(version_files, key=lambda p: p.name))
            digest = content_sha256(blob)
            total_size = sum(p.stat().st_size for p in version_files)

            doc = Document(
                doc_id=doc_id,
                tenant_id=tenant_id,
                created_by=owner,
                doc_group_id=doc_id,
                doc_name=title,
                doc_tag=tag,
                publish_status="published",
                index_status="pending",
                version_number=version_number,
                is_latest=True,
                content_sha256=digest,
                source_uri=str(primary.relative_to(root)),
                source_type=primary.suffix.lstrip(".") or None,
                doc_size=total_size,
                source_metadata={},
            )
            db.add(doc)
            db.flush()

            for path in version_files:
                ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                storage_key = str(path.relative_to(root))
                db.add(
                    DocumentFile(
                        tenant_id=tenant_id,
                        doc_id=doc_id,
                        version=version_number,
                        storage_key=storage_key,
                        filename=path.name,
                        content_type=ctype,
                        size_bytes=path.stat().st_size,
                    )
                )

            job = IndexJob(
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
                f"title={title!r} files={len(version_files)} job={job.id}"
            )

            if do_index:
                try:
                    process_index_job(db, job.id)
                    db.refresh(doc)
                    print(f"  indexed status={doc.index_status}")
                except Exception as exc:  # noqa: BLE001
                    print(f"  index failed: {exc}")

    print(f"done restored={restored}")


if __name__ == "__main__":
    restore(do_index="--index" in sys.argv)
