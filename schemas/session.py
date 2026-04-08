from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SessionStatus(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    ACTIVE = "ACTIVE"
    HANGING_UP = "HANGING_UP"
    ENDED = "ENDED"
    FAILED = "FAILED"


class TerminationCode(str, Enum):
    NORMAL_END = "normal_end"
    UPSTREAM_STOPPED = "upstream_stopped"
    PROVIDER_ERROR = "provider_error"
    RUNTIME_ERROR = "runtime_error"
    SILENCE_TIMEOUT = "silence_timeout"
    MAX_DURATION_REACHED = "max_duration_reached"
    INVALID_PROTOCOL = "invalid_protocol"
    CLIENT_DISCONNECTED = "client_disconnected"


class ConversationConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    language: str = "zh-CN"
    system_prompt: str
    initial_messages: list[dict[str, Any]] = Field(default_factory=list)


class MediaConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    encoding: str = "pcm_s16le"
    sample_rate: int = 8000
    channels: int = 1

    @field_validator("encoding")
    @classmethod
    def validate_encoding(cls, value: str) -> str:
        if value != "pcm_s16le":
            raise ValueError("V1 only supports pcm_s16le")
        return value

    @field_validator("sample_rate")
    @classmethod
    def validate_sample_rate(cls, value: int) -> int:
        if value != 8000:
            raise ValueError("V1 only supports 8000 Hz")
        return value

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, value: int) -> int:
        if value != 1:
            raise ValueError("V1 only supports mono audio")
        return value


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    barge_in: bool = True
    silence_timeout_ms: int = 6000
    max_session_duration_ms: int = 180000


class MetadataPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    tenant_id: str | None = None
    external_ref_id: str | None = None
    caller_e164: str | None = None
    callee_e164: str | None = None
