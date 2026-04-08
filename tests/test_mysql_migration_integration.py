from __future__ import annotations

import os
import subprocess

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_mysql_migration_creates_core_tables() -> None:
    if os.getenv("RUN_MYSQL_INTEGRATION") != "1":
        pytest.skip("Set RUN_MYSQL_INTEGRATION=1 to run MySQL integration tests")

    env = os.environ.copy()
    subprocess.run(["./.venv/bin/alembic", "upgrade", "head"], check=True, env=env)

    database_url = env.get(
        "DATABASE_URL",
        "mysql+asyncmy://agent_call:agent_call@127.0.0.1:3306/agent_call",
    )
    engine = create_async_engine(database_url, future=True)
    expected_tables = {
        "session_record",
        "event_log",
        "session_turn_metrics",
        "session_provider_metrics",
        "transcript_log",
    }
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                """
            )
        )
        existing = {row[0] for row in result.fetchall()}
    await engine.dispose()
    assert expected_tables.issubset(existing)
