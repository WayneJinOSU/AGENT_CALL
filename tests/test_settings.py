from __future__ import annotations

from settings import build_database_url


def test_build_database_url_prefers_explicit_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "mysql+asyncmy://u:p@h:3306/db?charset=utf8mb4")
    assert build_database_url() == "mysql+asyncmy://u:p@h:3306/db?charset=utf8mb4"


def test_build_database_url_from_mysql_db_fields(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_DIALECT", "mysql")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "3306")
    monkeypatch.setenv("DB_USER", "deepsearch")
    monkeypatch.setenv("DB_PASSWORD", "abc123")
    monkeypatch.setenv("DB_NAME", "AGENT_CALL")
    monkeypatch.setenv("DB_CHARSET", "utf8mb4")
    assert (
        build_database_url()
        == "mysql+asyncmy://deepsearch:abc123@localhost:3306/AGENT_CALL?charset=utf8mb4"
    )


def test_build_database_url_for_postgresql(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_DIALECT", "postgresql")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_USER", "pg_user")
    monkeypatch.setenv("DB_PASSWORD", "pg_pwd")
    monkeypatch.setenv("DB_NAME", "agent_call")
    assert build_database_url() == "postgresql+asyncpg://pg_user:pg_pwd@localhost:5432/agent_call"
