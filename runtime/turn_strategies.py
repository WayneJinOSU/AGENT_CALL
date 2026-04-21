"""Project-specific user turn strategy wrappers."""

from __future__ import annotations

from loguru import logger
from pipecat.frames.frames import InterimTranscriptionFrame, TranscriptionFrame
from pipecat.turns.user_start import MinWordsUserTurnStartStrategy

from runtime.processors.interrupt_deduper import InterruptDeduper


class LoggingMinWordsUserTurnStartStrategy(MinWordsUserTurnStartStrategy):
    """Min-words start strategy with explicit logs for blocked barge-in attempts."""

    def __init__(self, *, interrupt_deduper: InterruptDeduper | None = None, **kwargs):
        super().__init__(**kwargs)
        self._interrupt_deduper = interrupt_deduper

    async def _handle_transcription(self, frame: TranscriptionFrame | InterimTranscriptionFrame):
        min_words = self._min_words if self._bot_speaking else 1
        token_count = InterruptDeduper.count_tokens(frame.text)
        should_trigger = token_count >= min_words
        is_interim = isinstance(frame, InterimTranscriptionFrame)

        logger.debug(
            f"{self} should_trigger={should_trigger} num_spoken_tokens={token_count} "
            f"min_words={min_words} bot_speaking={self._bot_speaking} interim_transcription={is_interim}"
        )

        if not should_trigger and self._bot_speaking:
            logger.info(
                "MinWords blocked barge-in transcript={!r} num_spoken_tokens={} min_words={} interim_transcription={}",
                frame.text,
                token_count,
                min_words,
                is_interim,
            )
            return

        if not should_trigger:
            return

        if should_trigger:
            if self._bot_speaking and self._interrupt_deduper is not None:
                decision = self._interrupt_deduper.evaluate(
                    text=frame.text,
                    reason="barge_in",
                    phase="interim" if is_interim else "final",
                )
                if decision.action == "defer":
                    logger.info(
                        "InterruptDeduper deferred barge-in transcript={!r} similarity={} elapsed_ms={} candidate_reason={} candidate={!r} prefix_match={} normalized={!r}",
                        frame.text,
                        round(decision.similarity, 3),
                        decision.elapsed_ms,
                        decision.candidate_reason,
                        decision.candidate_text,
                        decision.prefix_match,
                        decision.normalized_text,
                    )
                    return
                if decision.action == "suppress":
                    logger.info(
                        "InterruptDeduper suppressed barge-in transcript={!r} similarity={} elapsed_ms={} candidate_reason={} candidate={!r} prefix_match={} normalized={!r}",
                        frame.text,
                        round(decision.similarity, 3),
                        decision.elapsed_ms,
                        decision.candidate_reason,
                        decision.candidate_text,
                        decision.prefix_match,
                        decision.normalized_text,
                    )
                    return
            await self.trigger_user_turn_started()
            if self._bot_speaking and self._interrupt_deduper is not None:
                self._interrupt_deduper.begin_accepted(
                    text=frame.text,
                    reason="barge_in",
                )
