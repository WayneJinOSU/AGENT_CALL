"""Emergency interruption helpers for manual and keyword-based barge-in."""

from __future__ import annotations

import re
import time
from collections.abc import Awaitable, Callable

from loguru import logger
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    InterimTranscriptionFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from runtime.processors.interrupt_deduper import InterruptDeduper

EmergencyInterruptHandler = Callable[[dict[str, str]], Awaitable[None]]


class EmergencyInterruptProcessor(FrameProcessor):
    """Trigger a high-priority interruption when explicit stop keywords appear."""

    _DEFAULT_KEYWORDS = (
        "停",
        "等一下",
        "等下",
        "别说了",
        "不要说了",
        "先别说",
        "暂停",
        "stop",
        "holdon",
        "wait",
    )

    _NORMALIZE_PATTERN = re.compile(r"[\s\.,!?;:，。！？；：、“”\"'‘’（）()\-_]+")

    def __init__(
        self,
        *,
        interrupt_handler: EmergencyInterruptHandler,
        cooldown_seconds: float = 1.5,
        interrupt_deduper: InterruptDeduper | None = None,
    ) -> None:
        super().__init__()
        self._interrupt_handler = interrupt_handler
        self._cooldown_seconds = cooldown_seconds
        self._interrupt_deduper = interrupt_deduper
        self._assistant_speaking = False
        self._last_interrupt_monotonic = 0.0

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, BotStartedSpeakingFrame):
            self._assistant_speaking = True
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._assistant_speaking = False
        elif isinstance(frame, (InterimTranscriptionFrame, TranscriptionFrame)) and self._assistant_speaking:
            matched_keyword = self._match_keyword(frame.text)
            now_monotonic = time.monotonic()
            if matched_keyword and self._can_trigger(now_monotonic):
                if self._interrupt_deduper is not None:
                    decision = self._interrupt_deduper.evaluate(
                        text=frame.text,
                        reason="keyword_interrupt",
                        phase="final" if isinstance(frame, TranscriptionFrame) else "interim",
                        now_monotonic=now_monotonic,
                        defer_on_interim=False,
                    )
                    if decision.action == "suppress":
                        logger.info(
                            "[EmergencyInterruptProcessor] Suppressed repeated keyword interrupt keyword={} similarity={} elapsed_ms={} candidate_reason={} candidate={!r} text={!r}",
                            matched_keyword,
                            round(decision.similarity, 3),
                            decision.elapsed_ms,
                            decision.candidate_reason,
                            decision.candidate_text,
                            frame.text,
                        )
                        await self.push_frame(frame, direction)
                        return
                self._last_interrupt_monotonic = now_monotonic
                logger.info(
                    "[EmergencyInterruptProcessor] Triggered keyword interrupt keyword={} transcript_type={} text={!r}",
                    matched_keyword,
                    "final" if isinstance(frame, TranscriptionFrame) else "interim",
                    frame.text,
                )
                await self._interrupt_handler(
                    {
                        "reason": "keyword_interrupt",
                        "keyword": matched_keyword,
                        "text": frame.text,
                        "transcript_type": "final" if isinstance(frame, TranscriptionFrame) else "interim",
                    }
                )
                if self._interrupt_deduper is not None:
                    self._interrupt_deduper.begin_accepted(
                        text=frame.text,
                        reason="keyword_interrupt",
                        now_monotonic=now_monotonic,
                    )

        await self.push_frame(frame, direction)

    def _can_trigger(self, now_monotonic: float) -> bool:
        return (now_monotonic - self._last_interrupt_monotonic) >= self._cooldown_seconds

    @classmethod
    def _match_keyword(cls, text: str) -> str | None:
        normalized = cls._NORMALIZE_PATTERN.sub("", text.lower())
        for keyword in cls._DEFAULT_KEYWORDS:
            if keyword in normalized:
                return keyword
        return None
