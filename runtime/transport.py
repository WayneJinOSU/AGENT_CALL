"""传输桥接层。

职责：
- 将北向控制帧插入 pipeline（SessionControlFrame）
- 把 session.stop 转为运行时停止动作
- 统一 FastAPIWebsocketTransport 初始化参数
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket
from pipecat.frames.frames import Frame, InputAudioRawFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport

from settings import settings


@dataclass
class SessionControlFrame(Frame):
    """Internal control frame generated from JSON control messages."""
    message_type: str
    request_id: str
    payload: dict[str, Any] = field(default_factory=dict)


StopHandler = Callable[[str], Awaitable[None]]
InputActivityHandler = Callable[[int], Awaitable[None]]


class SessionMessageRouter(FrameProcessor):
    """
    Lightweight control router inside pipeline.
    - handles session.stop
    - tracks inbound audio activity for silence policy/metrics
    """

    def __init__(
        self,
        *,
        stop_handler: StopHandler,
        input_activity_handler: InputActivityHandler | None = None,
    ) -> None:
        super().__init__()
        self._stop_handler = stop_handler
        self._input_activity_handler = input_activity_handler

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, SessionControlFrame):
            # session.stop does not continue downstream; it triggers orchestrator stop.
            if frame.message_type == "session.stop":
                reason = str(frame.payload.get("reason") or "upstream_stopped")
                await self._stop_handler(reason)
                return
            logging.debug("Ignoring unexpected control frame type=%s", frame.message_type)
            return

        if isinstance(frame, InputAudioRawFrame) and self._input_activity_handler:
            await self._input_activity_handler(len(frame.audio))

        await self.push_frame(frame, direction)


class SessionTransportAdapter:
    """Wrap FastAPIWebsocketTransport with project-wide media defaults."""

    def __init__(self, websocket: WebSocket, serializer) -> None:
        self.websocket = websocket
        self.serializer = serializer
        self.transport = FastAPIWebsocketTransport(
            websocket=websocket,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                audio_in_sample_rate=settings.default_audio_sample_rate,
                audio_out_sample_rate=settings.default_audio_sample_rate,
                audio_in_channels=settings.default_audio_channels,
                audio_out_channels=settings.default_audio_channels,
                add_wav_header=False,
                audio_in_passthrough=True,
                serializer=serializer,
            ),
        )

    @classmethod
    def create(cls, websocket: WebSocket) -> SessionTransportAdapter:
        from gateway.serializer import SessionProtocolFrameSerializer

        serializer = SessionProtocolFrameSerializer(
            sample_rate=settings.default_audio_sample_rate,
            input_sample_rate=settings.default_audio_sample_rate,
            output_sample_rate=settings.default_audio_sample_rate,
            channels=settings.default_audio_channels,
        )
        return cls(websocket=websocket, serializer=serializer)
