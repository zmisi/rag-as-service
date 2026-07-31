"""Alembic helpers used at process startup and in tests."""

from __future__ import annotations

import logging
import re

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from rag_api.config import get_settings
from rag_api.runtime_paths import get_api_root

logger = logging.getLogger(__name__)

_API_ROOT = get_api_root()


def _redact_url(url: str) -> str:
    """Hide password in logs: user:pass@ → user:***@"""
    return re.sub(r"(://[^:/@]+):([^@/]+)@", r"\1:***@", url)


def alembic_config(database_url: str | None = None) -> Config:
    """Build Alembic ``Config`` for the API package and optional database URL."""
    cfg = Config(str(_API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_ROOT / "alembic"))
    url = database_url or get_settings().database_url
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def run_migrations(*, database_url: str | None = None) -> None:
    """Apply pending migrations up to head(s)."""
    cfg = alembic_config(database_url)
    url = cfg.get_main_option("sqlalchemy.url") or ""
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    head_label = heads[0] if len(heads) == 1 else ",".join(heads)

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
            # Multiple branch tips may be present until a merge revision lands.
            currents = list(ctx.get_current_heads())
            current = currents[0] if len(currents) == 1 else ",".join(currents) or None
    finally:
        engine.dispose()

    logger.info(
        "Alembic target db=%s user=%s url=%s current=%s head=%s",
        db,
        role,
        _redact_url(url),
        current,
        head_label,
    )
    # "heads" applies all branch tips; after merge revision there is a single head.
    command.upgrade(cfg, "heads")
    logger.info("Alembic migrations complete (at head=%s)", head_label)


def upgrade_head() -> None:
    """Alias for tests and scripts."""
    run_migrations()
