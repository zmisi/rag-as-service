"""Alembic environment.

Uses DATABASE_URL / Settings; does not rely on ORM metadata for F01 DDL
(raw SQL migrations aligned with Feature Spec).
"""

from __future__ import annotations

from logging.config import fileConfig
import logging

from alembic import context
from sqlalchemy import engine_from_config, pool

from rag_api.config import get_settings

config = context.config

if config.config_file_name is not None:
    # Keep app loggers (uvicorn / rag_api) when migrations run at startup.
    fileConfig(config.config_file_name, disable_existing_loggers=False)
    # alembic.ini sets root to WARN; restore INFO for our package.
    logging.getLogger("rag_api").setLevel(logging.INFO)
    if not logging.getLogger("rag_api").handlers:
        logging.getLogger().setLevel(logging.INFO)


target_metadata = None


def get_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url and not url.startswith("driver://"):
        return url
    return get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="rag_service",
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Ensure schema exists before alembic_version table is created there
        connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS rag_service")
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema="rag_service",
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
