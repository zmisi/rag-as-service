#!/usr/bin/env python3
"""Idempotent local seed: tenant-a + owner user for F05 UI auth stub.

Usage (from repo root, venv active):

  python scripts/seed_dev_tenant.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_API_SRC = Path(__file__).resolve().parents[1] / "apps" / "api" / "src"
sys.path.insert(0, str(_API_SRC))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from rag_api.config import get_settings
from rag_api.db.models import Tenant, TenantMember, User

SUBDOMAIN = "tenant-a"
EMAIL = "owner-a@example.com"
PASSWORD_HASH = "dev-stub-not-for-login"  # F02 not wired; hash unused by auth stub
DISPLAY_NAME = "Tenant A (dev)"


def main() -> None:
    engine = create_engine(get_settings().database_url)
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == EMAIL))
        if user is None:
            user = User(email=EMAIL, password_hash=PASSWORD_HASH)
            db.add(user)
            db.flush()
            print(f"created user {EMAIL}")
        else:
            print(f"user exists {EMAIL}")

        tenant = db.scalar(select(Tenant).where(Tenant.subdomain == SUBDOMAIN))
        if tenant is None:
            tenant = Tenant(subdomain=SUBDOMAIN, display_name=DISPLAY_NAME)
            db.add(tenant)
            db.flush()
            print(f"created tenant {SUBDOMAIN}")
        else:
            print(f"tenant exists {SUBDOMAIN}")

        member = db.scalar(
            select(TenantMember).where(
                TenantMember.tenant_id == tenant.id,
                TenantMember.user_id == user.id,
            )
        )
        if member is None:
            db.add(TenantMember(tenant_id=tenant.id, user_id=user.id, role="owner"))
            print("created tenant_members owner link")
        else:
            print("membership exists")

        db.commit()
        print()
        print(f"NEXT_PUBLIC_DEV_USER_ID={user.id}")
        print(f"Host: http://{SUBDOMAIN}.lxzxai.com:3000/chat")


if __name__ == "__main__":
    main()
