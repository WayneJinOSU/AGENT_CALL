"""Session 相关 schema 与枚举。"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SessionStatus(str, Enum):
    """会话状态枚举。"""
    CREATED = "CREATED"
    READY = "READY"
    ACTIVE = "ACTIVE"
    HANGING_UP = "HANGING_UP"
    ENDED = "ENDED"
    FAILED = "FAILED"


class TerminationCode(str, Enum):
    """会话终止原因枚举。"""
    NORMAL_END = "normal_end"
    UPSTREAM_STOPPED = "upstream_stopped"
    PROVIDER_ERROR = "provider_error"
    RUNTIME_ERROR = "runtime_error"
    SILENCE_TIMEOUT = "silence_timeout"
    MAX_DURATION_REACHED = "max_duration_reached"
    INVALID_PROTOCOL = "invalid_protocol"
    CLIENT_DISCONNECTED = "client_disconnected"


class ConversationConfig(BaseModel):
    """会话文本上下文配置。"""
    model_config = ConfigDict(extra="ignore")

    language: str = "zh-CN"
    system_prompt: str
    initial_messages: list[dict[str, Any]] = Field(default_factory=list)


class MediaConfig(BaseModel):
    """媒体约束（V1 固定 8k/mono/pcm_s16le）。"""
    model_config = ConfigDict(extra="ignore")

    encoding: str = "pcm_s16le"
    sample_rate: int = 8000
    channels: int = 1

    @field_validator("encoding")
    @classmethod
    def validate_encoding(cls, value: str) -> str:
        """仅允许 PCM16 编码。"""
        if value != "pcm_s16le":
            raise ValueError("V1 only supports pcm_s16le")
        return value

    @field_validator("sample_rate")
    @classmethod
    def validate_sample_rate(cls, value: int) -> int:
        """仅允许 8k 采样率。"""
        if value != 8000:
            raise ValueError("V1 only supports 8000 Hz")
        return value

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, value: int) -> int:
        """仅允许单声道。"""
        if value != 1:
            raise ValueError("V1 only supports mono audio")
        return value


class RuntimeConfig(BaseModel):
    """会话运行时策略参数。"""
    model_config = ConfigDict(extra="ignore")

    barge_in: bool = True
    interrupt_repeat_similarity_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    interrupt_repeat_suppression_ms: int = Field(default=3000, ge=0)
    post_bot_grace_ms: int = Field(default=2000, ge=0)
    user_response_timeout_ms: int = Field(default=6000, ge=1)
    max_silence_follow_ups: int = Field(default=3, ge=1)
    max_session_duration_ms: int = Field(default=180000, ge=1)


class MetadataPayload(BaseModel):
    """透传业务元数据（不参与业务语义判断）。"""
    model_config = ConfigDict(extra="allow")

    tenant_id: str | None = None
    external_ref_id: str | None = None
    caller_e164: str | None = None
    callee_e164: str | None = None
