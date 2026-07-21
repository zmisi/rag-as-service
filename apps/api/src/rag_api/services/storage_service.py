"""Local filesystem storage for document source files (Phase 1)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from rag_api.config import get_settings


class StorageService:
    def __init__(self, root: Path | None = None) -> None:
        settings = get_settings()
        self.root = root or settings.storage_root
        self.root.mkdir(parents=True, exist_ok=True)

    def storage_key(
        self,
        *,
        tenant_id: UUID,
        document_id: UUID,
        version: str,
        filename: str,
    ) -> str:
        safe_name = Path(filename).name
        return f"{tenant_id}/{document_id}/{version}/{safe_name}"

    def write_bytes(self, storage_key: str, data: bytes) -> Path:
        path = self.root / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def read_bytes(self, storage_key: str) -> bytes:
        return (self.root / storage_key).read_bytes()

    def delete(self, storage_key: str) -> None:
        path = self.root / storage_key
        if path.is_file():
            path.unlink()
