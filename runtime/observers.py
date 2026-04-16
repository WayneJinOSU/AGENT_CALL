"""Pipecat Observer 桥接层。

把 pipeline 中的关键帧转换为：
- 实时存储写入（转写、turn 指标）
- 内存指标聚合（TTFB、usage、latency）
"""

from __future__ import annotations

from datetime import UTC, datetime

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    InterimTranscriptionFrame,
    InterruptionFrame,
    MetricsFrame,
    TextFrame,
    TranscriptionFrame,
)
from pipecat.metrics.metrics import LLMUsageMetricsData, ProcessingMetricsData, TTFBMetricsData, TurnMetricsData, TTSUsageMetricsData
from pipecat.observers.base_observer import BaseObserver
from pipecat.observers.base_observer import FramePushed

from runtime.metrics import RuntimeMetricsCollector
from storage.repositories import Repositories


class RuntimePersistenceObserver(BaseObserver):
    """将运行时帧事件持久化并更新 RuntimeMetricsCollector。"""

    def __init__(
        self,
        *,
        session_id: str,
        repositories: Repositories,
        metrics_collector: RuntimeMetricsCollector,
        ready_event,
    ) -> None:
        super().__init__()
        self._session_id = session_id
        self._repositories = repositories
        self._metrics = metrics_collector
        self._ready_event = ready_event
        self._seen_frames: set[int] = set()

    async def on_pipeline_started(self) -> None:
        """pipeline 就绪后通知 session.runner 发送 session.ready。"""
        self._ready_event.set()

    async def on_push_frame(self, data: FramePushed) -> None:
        """按帧类型分发持久化/聚合逻辑。"""
        frame = data.frame
        if frame.id in self._seen_frames:
            # 去重：同一 frame 只处理一次，避免重复写库。
            return
        self._seen_frames.add(frame.id)

        if isinstance(frame, InterimTranscriptionFrame):
            await self._repositories.transcripts.create(
                session_id=self._session_id,
                speaker="user",
                transcript_type="interim",
                text=frame.text,
                turn_id=self._metrics.active_turn.turn_id if self._metrics.active_turn else None,
                sequence=getattr(frame, "id", 0),
                metadata={"user_id": frame.user_id, "timestamp": frame.timestamp},
            )
            return

        if isinstance(frame, TranscriptionFrame):
            await self._repositories.transcripts.create(
                session_id=self._session_id,
                speaker="user",
                transcript_type="final",
                text=frame.text,
                turn_id=self._metrics.active_turn.turn_id if self._metrics.active_turn else None,
                sequence=getattr(frame, "id", 0),
                metadata={"user_id": frame.user_id, "timestamp": frame.timestamp},
            )
            return

        if isinstance(frame, BotStartedSpeakingFrame):
            self._metrics.start_assistant_turn()
            return

        if isinstance(frame, InterruptionFrame):
            self._metrics.mark_active_turn_interrupted()
            return

        if isinstance(frame, TextFrame):
            self._metrics.record_text_chars(len(frame.text))
            await self._repositories.transcripts.create(
                session_id=self._session_id,
                speaker="assistant",
                transcript_type="final",
                text=frame.text,
                turn_id=self._metrics.active_turn.turn_id if self._metrics.active_turn else None,
                sequence=getattr(frame, "id", 0),
                metadata=None,
            )
            return

        if isinstance(frame, BotStoppedSpeakingFrame):
            turn = self._metrics.finish_assistant_turn()
            if turn:
                await self._repositories.turn_metrics.upsert(
                    session_id=self._session_id,
                    turn_id=turn.turn_id,
                    turn_index=turn.turn_index,
                    speaker=turn.speaker,
                    started_at=turn.started_at,
                    ended_at=turn.ended_at or datetime.now(UTC),
                    interrupted=turn.interrupted,
                    asr_ttfb_ms=turn.asr_ttfb_ms,
                    llm_ttfb_ms=turn.llm_ttfb_ms,
                    tts_ttfb_ms=turn.tts_ttfb_ms,
                    e2e_latency_ms=turn.e2e_latency_ms,
                    text_chars=turn.text_chars,
                    metadata=None,
                )
            return

        if isinstance(frame, MetricsFrame):
            # 统一把 Pipecat metrics 映射到 capability 维度。
            for item in frame.data:
                processor_name = item.processor.lower()
                capability = "llm"
                if "tts" in processor_name:
                    capability = "tts"
                elif "stt" in processor_name or "asr" in processor_name:
                    capability = "asr"
                if isinstance(item, TTFBMetricsData):
                    self._metrics.record_ttfb(capability, item.value)
                elif isinstance(item, ProcessingMetricsData):
                    self._metrics.record_processing_time(capability, item.value)
                elif isinstance(item, TurnMetricsData):
                    self._metrics.record_turn_latency(item.e2e_processing_time_ms)
                elif isinstance(item, LLMUsageMetricsData):
                    snapshot = self._metrics.provider_metrics.get("llm")
                    if snapshot:
                        snapshot.usage_input += item.value.prompt_tokens
                        snapshot.usage_output += item.value.completion_tokens
                elif isinstance(item, TTSUsageMetricsData):
                    snapshot = self._metrics.provider_metrics.get("tts")
                    if snapshot:
                        snapshot.usage_output += item.value
