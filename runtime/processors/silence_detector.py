"""Detect post-bot silence windows and emit follow-up events."""

from __future__ import annotations

import asyncio
import contextlib

from pipecat.frames.frames import BotStartedSpeakingFrame, BotStoppedSpeakingFrame, EndFrame, Frame, UserStartedSpeakingFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class SilenceDetector(FrameProcessor):
    """Track user-response silence after bot speech and emit round-based events."""

    def __init__(
        self,
        *,
        post_bot_grace_ms: int,
        user_response_timeout_ms: int,
        max_silence_follow_ups: int,
    ) -> None:
        super().__init__()
        self._post_bot_grace_seconds = post_bot_grace_ms / 1000
        self._user_response_timeout_seconds = user_response_timeout_ms / 1000
        self._max_silence_follow_ups = max_silence_follow_ups
        self._silence_count = 0
        self._silence_task: asyncio.Task | None = None
        self._closed = False
        self._register_event_handler("on_silence_detected", sync=True)

    @property
    def max_silence_follow_ups(self) -> int:
        return self._max_silence_follow_ups

    async def disable(self) -> None:
        """Stop tracking and cancel any pending silence wait."""
        self._closed = True
        await self._cancel_silence_wait()

    async def cleanup(self):
        await self.disable()
        await super().cleanup()

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, EndFrame):
            await self.disable()
        elif isinstance(frame, UserStartedSpeakingFrame) and direction == FrameDirection.DOWNSTREAM:
            await self._reset_after_user_response()
        elif isinstance(frame, BotStartedSpeakingFrame) and direction == FrameDirection.UPSTREAM:
            await self._cancel_silence_wait()
        elif isinstance(frame, BotStoppedSpeakingFrame) and direction == FrameDirection.UPSTREAM:
            await self._arm_silence_wait()

        await self.push_frame(frame, direction)

    async def _reset_after_user_response(self) -> None:
        self._silence_count = 0
        await self._cancel_silence_wait()

    async def _arm_silence_wait(self) -> None:
        if self._closed:
            return
        await self._cancel_silence_wait()
        self._silence_task = asyncio.create_task(self._wait_for_user_response())

    async def _cancel_silence_wait(self) -> None:
        task = self._silence_task
        self._silence_task = None
        if not task or task.done():
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def _wait_for_user_response(self) -> None:
        current_task = asyncio.current_task()
        try:
            await asyncio.sleep(self._post_bot_grace_seconds)
            await asyncio.sleep(self._user_response_timeout_seconds)
            self._silence_count += 1
            await self._call_event_handler("on_silence_detected", self._silence_count)
        except asyncio.CancelledError:
            raise
        finally:
            if self._silence_task is current_task:
                self._silence_task = None
