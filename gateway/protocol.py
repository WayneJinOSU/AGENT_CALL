from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from schemas.messages import (
    SessionFailedMessage,
    SessionFinalizedMessage,
    SessionReadyMessage,
    SessionStartMessage,
    SessionStopMessage,
)


class ProtocolError(ValueError):
    pass


def parse_text_message(raw: str) -> SessionStartMessage | SessionStopMessage:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProtocolError("Invalid JSON message") from exc

    message_type = data.get("type")
    try:
        if message_type == "session.start":
            return SessionStartMessage.model_validate(data)
        if message_type == "session.stop":
            return SessionStopMessage.model_validate(data)
    except ValidationError as exc:
        raise ProtocolError(str(exc)) from exc
    raise ProtocolError(f"Unsupported message type: {message_type!r}")


def json_payload(message: SessionReadyMessage | SessionFailedMessage | SessionFinalizedMessage) -> dict[str, Any]:
    return message.model_dump(mode="json")


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()

