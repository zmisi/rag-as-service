"""Resolve application resources in source and installed-wheel environments."""

from __future__ import annotations

import os
from pathlib import Path

_API_ROOT_ENV = "RAG_API_ROOT"


def get_api_root() -> Path:
    """Return the API resource root, honoring the container path override."""
    configured = os.getenv(_API_ROOT_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def get_repo_root(api_root: Path | None = None) -> Path:
    """Return the monorepo root in source checkouts or the API root in images."""
    resolved_api_root = api_root or get_api_root()
    if resolved_api_root.name == "api" and resolved_api_root.parent.name == "apps":
        return resolved_api_root.parent.parent
    return resolved_api_root
