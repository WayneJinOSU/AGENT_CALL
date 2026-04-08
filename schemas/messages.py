from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.provider import ProviderSelection
from schemas.session import ConversationConfig, MediaConfig, MetadataPayload, RuntimeConfig, SessionStatus, TerminationCode


class SessionStartPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_type: str = "outbound_voice"
    conversation: ConversationConfig
    media: MediaConfig
    providers: ProviderSelection
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    metadata: MetadataPayload = Field(default_factory=MetadataPayload)


class SessionStartMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["session.start"]
    request_id: str
    payload: SessionStartPayload


class SessionStopPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str
    reason: str


class SessionStopMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["session.stop"]
    request_id: str
    payload: SessionStopPayload


class SessionReadyPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    media: MediaConfig


class SessionReadyMessage(BaseModel):
    type: Literal["session.ready"] = "session.ready"
    session_id: str
    trace_id: str
    timestamp: str
    payload: SessionReadyPayload


class SessionFailedPayload(BaseModel):
    status: SessionStatus = SessionStatus.FAILED
    termination_code: TerminationCode
    detail: str | None = None


class SessionFailedMessage(BaseModel):
    type: Literal["session.failed"] = "session.failed"
    session_id: str
    trace_id: str
    timestamp: str
    payload: SessionFailedPayload


class SessionFinalizedPayload(BaseModel):
    status: SessionStatus
    termination_code: TerminationCode
    turn_count: int
    total_duration_ms: int
    metadata: dict[str, Any] | None = None


class SessionFinalizedMessage(BaseModel):
    type: Literal["session.finalized"] = "session.finalized"
    session_id: str
    trace_id: str
    timestamp: str
    payload: SessionFinalizedPayload

