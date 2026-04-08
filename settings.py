from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    app_name: str = "AGENT_CALL"
    database_url: str = os.getenv(
        "DATABASE_URL",
        "mysql+asyncmy://agent_call:agent_call@127.0.0.1:3306/agent_call",
    )
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
    enable_reference_fallback: bool = os.getenv("ENABLE_REFERENCE_FALLBACK", "true").lower() == "true"


settings = Settings()
