#!/usr/bin/env python3
"""Idempotent seed: F12 widget site key for tenant-a harness.

Usage (from repo root, venv active):

  python scripts/seed_widget_site_key.py

Prints NEXT_PUBLIC_WIDGET_SITE_KEY=pk_... for apps/web .env.local
"""

from __future__ import annotations

import sys
from pathlib import Path

_API_SRC = Path(__file__).resolve().parents[1] / "apps" / "api" / "src"
sys.path.insert(0, str(_API_SRC))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from rag_api.config import get_settings
from rag_api.db.models import Tenant, WidgetSiteKey
from rag_api.db.models.widget_site_key import STATUS_ACTIVE
from rag_api.services.widget_site_keys import create_site_key

SUBDOMAIN = "tenant-a"
DEFAULT_ORIGINS = [
    "http://tenant-a.lxzxai.com:3000",
    "https://tenant-a.lxzxai.com",
]
KEY_NAME = "dev-harness"


def main() -> None:
    engine = create_engine(get_settings().database_url)
    with Session(engine) as db:
        tenant = db.scalar(select(Tenant).where(Tenant.tenant_name == SUBDOMAIN))
        if tenant is None:
            print(f"tenant {SUBDOMAIN} not found; run scripts/seed_dev_tenant.py first")
            sys.exit(1)

        existing = db.scalar(
            select(WidgetSiteKey).where(
                WidgetSiteKey.tenant_id == tenant.tenant_id,
                WidgetSiteKey.name == KEY_NAME,
                WidgetSiteKey.status == STATUS_ACTIVE,
            )
        )
        if existing is not None:
            # Refresh origins for local harness
            existing.allowed_origins = list(DEFAULT_ORIGINS)
            db.commit()
            db.refresh(existing)
            row = existing
            print(f"updated existing site key {row.public_key}")
        else:
            row = create_site_key(
                db,
                tenant_id=tenant.tenant_id,
                allowed_origins=DEFAULT_ORIGINS,
                name=KEY_NAME,
            )
            print(f"created site key {row.public_key}")

        print()
        print(f"NEXT_PUBLIC_WIDGET_SITE_KEY={row.public_key}")
        print(f"harness: http://{SUBDOMAIN}.lxzxai.com:3000/widget")
        print(f"admin:   http://{SUBDOMAIN}.lxzxai.com:3000/admin/widget")


if __name__ == "__main__":
    main()
