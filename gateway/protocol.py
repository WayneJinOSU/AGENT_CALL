"""北向控制消息协议工具。

负责：
- 解析 JSON 控制帧（session.start / session.stop）
- 统一抛出协议层错误
- 序列化下行消息
"""

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
    """协议格式错误。"""
    pass


def parse_text_message(raw: str) -> SessionStartMessage | SessionStopMessage:
    """将原始文本帧解析为结构化控制消息。"""
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
    """Pydantic 对象转为可下发 JSON dict。"""
    return message.model_dump(mode="json")


def utc_now_iso() -> str:
    """返回 UTC ISO 时间戳。"""
    return datetime.now(UTC).isoformat()
