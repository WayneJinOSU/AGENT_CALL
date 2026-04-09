from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import quote_plus

from dotenv import load_dotenv


load_dotenv()


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def build_database_url() -> str:
    explicit_url = os.getenv("DATABASE_URL")
    if explicit_url:
        return explicit_url

    dialect = (os.getenv("DB_DIALECT", "mysql") or "mysql").strip().lower()
    host = os.getenv("DB_HOST", "127.0.0.1")
    user = os.getenv("DB_USER", "agent_call")
    password = os.getenv("DB_PASSWORD", "agent_call")
    db_name = os.getenv("DB_NAME", "agent_call")
    charset = os.getenv("DB_CHARSET", "utf8mb4")

    if dialect in {"mysql", "mariadb"}:
        driver = "mysql+asyncmy"
        port = _int_env("DB_PORT", 3306)
        query = f"?charset={quote_plus(charset)}" if charset else ""
    elif dialect in {"postgresql", "postgres", "pgsql"}:
        driver = "postgresql+asyncpg"
        port = _int_env("DB_PORT", 5432)
        query = ""
    else:
        raise ValueError(f"Unsupported DB_DIALECT: {dialect!r}")

    user_escaped = quote_plus(user)
    if password:
        auth = f"{user_escaped}:{quote_plus(password)}"
    else:
        auth = user_escaped

    return f"{driver}://{auth}@{host}:{port}/{db_name}{query}"


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    app_name: str = "AGENT_CALL"
    db_dialect: str = os.getenv("DB_DIALECT", "mysql")
    db_host: str = os.getenv("DB_HOST", "127.0.0.1")
    db_port: int = _int_env("DB_PORT", 3306)
    db_user: str = os.getenv("DB_USER", "agent_call")
    db_name: str = os.getenv("DB_NAME", "agent_call")
    db_charset: str = os.getenv("DB_CHARSET", "utf8mb4")
    database_url: str = field(default_factory=build_database_url)
    initial_bot_text: str = os.getenv(
        "INITIAL_BOT_TEXT",
        "您好，这里是 AGENT_CALL。",
    )
    default_audio_encoding: str = "pcm_s16le"
    default_audio_sample_rate: int = 8000
    default_audio_channels: int = 1
    default_session_type: str = "outbound_voice"
    output_wave_frequency_hz: int = 440
    output_wave_gain: float = 0.15
    reference_provider_name: str = os.getenv("REFERENCE_PROVIDER_NAME", "reference")
    enable_reference_fallback: bool = _bool_env("ENABLE_REFERENCE_FALLBACK", True)


settings = Settings()
