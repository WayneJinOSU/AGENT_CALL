from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

from schemas.messages import SessionStartPayload
from schemas.session import SessionStatus, TerminationCode


@dataclass
class SessionContext:
    session_id: str
    trace_id: str
    websocket: WebSocket
    start_payload: SessionStartPayload
    status: SessionStatus = SessionStatus.CREATED
    termination_code: TerminationCode | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ready_at: datetime | None = None
    active_at: datetime | None = None
    ended_at: datetime | None = None
    sequence: int = 0
    turn_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence

