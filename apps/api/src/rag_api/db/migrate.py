"""Alembic helpers used at process startup and in tests."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from rag_api.config import get_settings

logger = logging.getLogger(__name__)

_API_ROOT = Path(__file__).resolve().parents[3]


def _redact_url(url: str) -> str:
    """Hide password in logs: user:pass@ → user:***@"""
    return re.sub(r"(://[^:/@]+):([^@/]+)@", r"\1:***@", url)


def alembic_config(database_url: str | None = None) -> Config:
    cfg = Config(str(_API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_ROOT / "alembic"))
    url = database_url or get_settings().database_url
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def run_migrations(*, database_url: str | None = None) -> None:
    """Apply pending migrations up to head."""
    cfg = alembic_config(database_url)
    url = cfg.get_main_option("sqlalchemy.url") or ""
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()

    engine = create_engine(
        url,
        connect_args={"options": "-csearch_path=rag_service,public"},
    )
    try:
        with engine.connect() as conn:
            db, role = conn.execute(
                text("SELECT current_database(), current_user")
            ).one()
            ctx = MigrationContext.configure(
                conn,
                opts={"version_table_schema": "rag_service"},
            )
            current = ctx.get_current_revision()
    finally:
        engine.dispose()

    logger.info(
        "Alembic target db=%s user=%s url=%s current=%s head=%s",
        db,
        role,
        _redact_url(url),
        current,
        head,
    )
    command.upgrade(cfg, "head")
    logger.info("Alembic migrations complete (at head=%s)", head)


def upgrade_head() -> None:
    """Alias for tests and scripts."""
    run_migrations()
