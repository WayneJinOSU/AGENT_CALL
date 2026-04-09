"""内部事件 schema。"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventType(str, Enum):
    """内部事件类型。"""
    SESSION_CREATED = "session.created"
    SESSION_READY = "session.ready"
    RUNTIME_STARTED = "runtime.started"
    RUNTIME_FAILED = "runtime.failed"
    SESSION_ENDED = "session.ended"
    SESSION_FAILED = "session.failed"
    SESSION_FINALIZED = "session.finalized"


class EventEnvelope(BaseModel):
    """统一事件信封。"""
    model_config = ConfigDict(extra="ignore")

    event_type: EventType
    sequence: int
    payload: dict[str, Any] = Field(default_factory=dict)
