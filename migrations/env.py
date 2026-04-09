"""Alembic 环境入口（异步引擎版）。"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from settings import settings
from storage.models import Base


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic's ConfigParser treats `%` as interpolation markers.
# Escape them so URL-encoded passwords (e.g. `%40`) work correctly.
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式迁移。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations_sync(connection) -> None:
    """在线模式下的同步迁移执行体（由 run_sync 调用）。"""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_migrations_online() -> None:
    """在线模式迁移（async engine）。"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_run_migrations_sync)
    await connectable.dispose()


def run_migrations_online() -> None:
    """在线迁移入口。"""
    asyncio.run(_run_migrations_online())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
