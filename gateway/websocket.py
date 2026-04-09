"""北向 WebSocket 路由。

约束：
- 连接后的第一条文本消息必须是 session.start
- 通过后把会话执行委托给 session.runner
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from gateway.protocol import ProtocolError, parse_text_message
from session.runner import run_session


router = APIRouter()


@router.websocket("/v1/outbound/session")
async def outbound_session(websocket: WebSocket) -> None:
    """单会话 WebSocket 入口。"""
    await websocket.accept()
    try:
        first_message = await websocket.receive_text()
    except WebSocketDisconnect:
        return

    try:
        parsed = parse_text_message(first_message)
    except ProtocolError:
        await websocket.close(code=1003, reason="Invalid protocol")
        return

    if parsed.type != "session.start":
        await websocket.close(code=1003, reason="Expected session.start as first frame")
        return

    await run_session(websocket, parsed)
