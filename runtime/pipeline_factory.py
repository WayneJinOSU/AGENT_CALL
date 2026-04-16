"""Pipecat Pipeline 装配工厂。"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADAnalyzer, VADParams
from pipecat.observers.loggers.metrics_log_observer import MetricsLogObserver
from pipecat.observers.startup_timing_observer import StartupTimingObserver
from pipecat.observers.turn_tracking_observer import TurnTrackingObserver
from pipecat.observers.user_bot_latency_observer import UserBotLatencyObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair, LLMUserAggregatorParams
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.turns.user_mute import (
    AlwaysUserMuteStrategy,
    FunctionCallUserMuteStrategy,
    MuteUntilFirstBotCompleteUserMuteStrategy,
)

from runtime.observers import RuntimePersistenceObserver
from runtime.processors import SilenceDetector, VoicemailDetector, WordAwareSanitizer
from runtime.transport import SessionMessageRouter, SessionTransportAdapter
from session.context import SessionContext

INTERRUPTIBLE_VAD_STOP_SECS = 0.5
NON_INTERRUPTIBLE_VAD_STOP_SECS = 1.0
INTERRUPTIBLE_USER_TURN_STOP_TIMEOUT_SECS = 2.0
NON_INTERRUPTIBLE_USER_TURN_STOP_TIMEOUT_SECS = 5.0


@dataclass
class PipelineResources:
    """返回给 runner 的 pipeline 运行对象集合。"""
    task: PipelineTask
    context: LLMContext
    hangup_sanitizer: WordAwareSanitizer


def _build_vad_analyzer(*, sample_rate: int, allow_interruptions: bool) -> VADAnalyzer | None:
    """Create a session-scoped VAD analyzer for user turn detection."""
    stop_secs = INTERRUPTIBLE_VAD_STOP_SECS if allow_interruptions else NON_INTERRUPTIBLE_VAD_STOP_SECS
    try:
        return SileroVADAnalyzer(
            sample_rate=sample_rate,
            params=VADParams(stop_secs=stop_secs),
        )
    except Exception as exc:  # pragma: no cover - defensive fallback for optional runtime deps
        logger.warning("Failed to initialize Silero VAD analyzer, falling back to transcription-only turns: {}", exc)
        return None


def build_user_aggregator_params(*, allow_interruptions: bool, sample_rate: int) -> LLMUserAggregatorParams:
    """Build coordinated interruption behavior for the user aggregator."""
    if allow_interruptions:
        mute_strategies = [
            # Preserve the existing first-greeting protection while enabling barge-in afterwards.
            MuteUntilFirstBotCompleteUserMuteStrategy(),
            FunctionCallUserMuteStrategy(),
        ]
        user_turn_stop_timeout = INTERRUPTIBLE_USER_TURN_STOP_TIMEOUT_SECS
    else:
        mute_strategies = [
            AlwaysUserMuteStrategy(),
            FunctionCallUserMuteStrategy(),
        ]
        user_turn_stop_timeout = NON_INTERRUPTIBLE_USER_TURN_STOP_TIMEOUT_SECS

    return LLMUserAggregatorParams(
        user_mute_strategies=mute_strategies,
        user_turn_stop_timeout=user_turn_stop_timeout,
        vad_analyzer=_build_vad_analyzer(
            sample_rate=sample_rate,
            allow_interruptions=allow_interruptions,
        ),
    )


def build_pipeline_task(
    *,
    session_context: SessionContext,
    transport_adapter: SessionTransportAdapter,
    router: SessionMessageRouter,
    silence_detector: SilenceDetector,
    stt_service,
    llm_service,
    tts_service,
    persistence_observer: RuntimePersistenceObserver,
) -> PipelineResources:
    """根据 session 配置装配完整 PipelineTask。"""
    message_history = [
        {"role": "system", "content": session_context.start_payload.conversation.system_prompt},
        *session_context.start_payload.conversation.initial_messages,
    ]
    context = LLMContext(message_history)
    user_params = build_user_aggregator_params(
        allow_interruptions=session_context.start_payload.runtime.barge_in,
        sample_rate=session_context.start_payload.media.sample_rate,
    )
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(context, user_params=user_params)
    voicemail_detector = VoicemailDetector(language=session_context.start_payload.conversation.language)
    hangup_sanitizer = WordAwareSanitizer()
    audio_buffer = AudioBufferProcessor(
        sample_rate=session_context.start_payload.media.sample_rate,
        num_channels=session_context.start_payload.media.channels,
    )

    pipeline = Pipeline(
        [
            # 固定 V1 主链路：input -> stt -> llm -> tts -> output。
            # 在 STT/LLM 与 LLM/TTS 之间插入文本级控制处理器。
            transport_adapter.transport.input(),
            router,
            silence_detector,
            stt_service,
            voicemail_detector,
            user_aggregator,
            llm_service,
            hangup_sanitizer,
            tts_service,
            transport_adapter.transport.output(),
            assistant_aggregator,
            audio_buffer,
        ]
    )
    params = PipelineParams(
        allow_interruptions=session_context.start_payload.runtime.barge_in,
        enable_metrics=True,
        enable_usage_metrics=True,
        audio_in_sample_rate=session_context.start_payload.media.sample_rate,
        audio_out_sample_rate=session_context.start_payload.media.sample_rate,
    )
    task = PipelineTask(
        pipeline,
        params=params,
        enable_tracing=True,
        enable_turn_tracking=True,
        observers=[
            persistence_observer,
            MetricsLogObserver(),
            TurnTrackingObserver(),
            UserBotLatencyObserver(),
            StartupTimingObserver(),
        ],
    )
    return PipelineResources(task=task, context=context, hangup_sanitizer=hangup_sanitizer)
