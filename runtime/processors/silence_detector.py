"""Detect post-bot silence windows and emit follow-up events."""

from __future__ import annotations

import asyncio
import contextlib
import time

from loguru import logger
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
        self._wait_generation = 0
        self._last_arm_monotonic: float | None = None
        self._last_bot_started_monotonic: float | None = None
        self._last_bot_stopped_monotonic: float | None = None
        self._register_event_handler("on_silence_detected", sync=True)
        logger.info(
            "[SilenceDetector] Initialized: grace={}ms timeout={}ms max_follow_ups={}",
            post_bot_grace_ms,
            user_response_timeout_ms,
            max_silence_follow_ups,
        )

    @property
    def max_silence_follow_ups(self) -> int:
        return self._max_silence_follow_ups

    async def disable(self) -> None:
        """Stop tracking and cancel any pending silence wait."""
        self._closed = True
        logger.info("[SilenceDetector] Disabled")
        await self._cancel_silence_wait()

    async def cleanup(self):
        await self.disable()
        await super().cleanup()

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, EndFrame):
            logger.info("[SilenceDetector] Received EndFrame; disabling silence tracking")
            await self.disable()
        elif isinstance(frame, UserStartedSpeakingFrame):
            logger.info("[SilenceDetector] UserStartedSpeakingFrame received; resetting silence wait")
            await self._reset_after_user_response()
        elif isinstance(frame, BotStartedSpeakingFrame) and direction == FrameDirection.UPSTREAM:
            self._last_bot_started_monotonic = time.monotonic()
            logger.info(
                "[SilenceDetector] BotStartedSpeakingFrame received; cancelling silence wait (since_last_stop={:.3f}s)",
                self._elapsed_since(self._last_bot_stopped_monotonic),
            )
            await self._cancel_silence_wait()
        elif isinstance(frame, BotStoppedSpeakingFrame) and direction == FrameDirection.UPSTREAM:
            self._last_bot_stopped_monotonic = time.monotonic()
            logger.info(
                "[SilenceDetector] BotStoppedSpeakingFrame received; arming silence wait (since_last_start={:.3f}s)",
                self._elapsed_since(self._last_bot_started_monotonic),
            )
            await self._arm_silence_wait()

        await self.push_frame(frame, direction)

    async def _reset_after_user_response(self) -> None:
        self._silence_count = 0
        await self._cancel_silence_wait()

    async def _arm_silence_wait(self) -> None:
        if self._closed:
            logger.info("[SilenceDetector] Skip arming silence wait because detector is closed")
            return
        await self._cancel_silence_wait()
        self._wait_generation += 1
        self._last_arm_monotonic = time.monotonic()
        logger.info(
            "[SilenceDetector] Arming silence wait gen={} grace={:.3f}s timeout={:.3f}s",
            self._wait_generation,
            self._post_bot_grace_seconds,
            self._user_response_timeout_seconds,
        )
        self._silence_task = asyncio.create_task(self._wait_for_user_response())

    async def _cancel_silence_wait(self) -> None:
        task = self._silence_task
        self._silence_task = None
        if not task or task.done():
            return
        logger.info(
            "[SilenceDetector] Cancelling silence wait gen={} after {:.3f}s",
            self._wait_generation,
            self._elapsed_since(self._last_arm_monotonic),
        )
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def _wait_for_user_response(self) -> None:
        current_task = asyncio.current_task()
        generation = self._wait_generation
        try:
            await asyncio.sleep(self._post_bot_grace_seconds)
            await asyncio.sleep(self._user_response_timeout_seconds)
            self._silence_count += 1
            logger.info(
                "[SilenceDetector] Silence timeout fired gen={} silence_count={} elapsed={:.3f}s",
                generation,
                self._silence_count,
                self._elapsed_since(self._last_arm_monotonic),
            )
            await self._call_event_handler("on_silence_detected", self._silence_count)
        except asyncio.CancelledError:
            logger.info("[SilenceDetector] Silence wait task cancelled gen={}", generation)
            raise
        finally:
            if self._silence_task is current_task:
                self._silence_task = None

    @staticmethod
    def _elapsed_since(start: float | None) -> float:
        if start is None:
            return -1.0
        return time.monotonic() - start
