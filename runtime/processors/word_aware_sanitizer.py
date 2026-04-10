"""Detect assistant farewell keywords and terminate the session gracefully."""

from __future__ import annotations

import asyncio
import re

from loguru import logger
from pipecat.frames.frames import EndFrame, Frame, LLMFullResponseEndFrame, LLMTextFrame, TextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class WordAwareSanitizer(FrameProcessor):
    """Watch LLM text stream and end call after assistant farewell phrase."""

    _COMPACT_ENDCALL_REGEX = re.compile(r"(?:goodbye|adiós|adios|hastaluego|nosvemos|chao|chau|再见|拜拜|挂了|\[\[HANGUP\]\])", re.I)

    def __init__(
        self,
        *,
        max_buffer_chars: int = 600,
        exit_delay: float = 1.5,
        debug_stream: bool = False,
    ) -> None:
        super().__init__()
        self._buffer = ""
        self._max_buffer_chars = max_buffer_chars
        self._exit_delay = exit_delay
        self._debug_stream = debug_stream
        self._is_hanging_up = False
        self._is_ended = False
        self._endcall_regex = re.compile(
            r"(?i)("
            r"\b(?:goodbye|bye|bye-bye|see you|have a great day|have a good one)\b|"
            r"\b(?:adi[oó]s|hasta\s+(?:luego|mañana|pronto)|nos\s+vemos|chao|chau|cu[ií]date)\b|"
            r"\bque\s+tenga\s+(?:un\s+)?(?:lindo|buen|excelente)\s+d[ií]a\b|"
            r"(?:再见|拜拜|挂了)|"
            r"\[\[HANGUP\]\]"
            r")"
        )

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        def _get_text_payload(candidate: Frame) -> str | None:
            if isinstance(candidate, (LLMTextFrame, TextFrame)):
                return (candidate.text or "").strip()
            return None

        if self._is_hanging_up:
            # Let control frames pass through so downstream can finish the current turn.
            if isinstance(frame, EndFrame):
                self._is_ended = True
            if not isinstance(frame, (LLMTextFrame, TextFrame)):
                await self.push_frame(frame, direction)
            return

        text = _get_text_payload(frame)
        if text is not None:
            if text:
                self._buffer += text
                if len(self._buffer) > self._max_buffer_chars:
                    self._buffer = self._buffer[-self._max_buffer_chars :]
                check_text = self._buffer.strip()
                compact_text = self._compact_text(check_text)
                if self._debug_stream and self._should_log_debug(text):
                    logger.debug(
                        "[WordAwareSanitizer] Inspecting {} text: {}",
                        type(frame).__name__,
                        check_text[-120:],
                    )
                if self._endcall_regex.search(check_text) or self._COMPACT_ENDCALL_REGEX.search(compact_text):
                    logger.info(
                        "[WordAwareSanitizer] Detected end phrase from {}; start hangup sequence.",
                        type(frame).__name__,
                    )
                    self._is_hanging_up = True
                    self.create_task(self._perform_hangup_sequence(direction), "hangup_sequence")
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, (LLMFullResponseEndFrame, EndFrame)):
            if isinstance(frame, EndFrame):
                self._is_ended = True
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)

    async def _perform_hangup_sequence(self, direction: FrameDirection) -> None:
        try:
            await asyncio.sleep(self._exit_delay)
            if not self._is_ended:
                logger.info("[WordAwareSanitizer] pushing EndFrame")
                self._is_ended = True
                await self.push_frame(EndFrame(), direction)
        except Exception as exc:
            logger.exception("[WordAwareSanitizer] Hangup sequence error: {}", exc)

    @staticmethod
    def _compact_text(text: str) -> str:
        return re.sub(r"\s+", "", text)

    @staticmethod
    def _should_log_debug(text: str) -> bool:
        return bool(text and (len(text) >= 8 or re.search(r"[.!?。！？；;]$", text)))
