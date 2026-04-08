from __future__ import annotations

from dataclasses import dataclass

from pipecat.observers.loggers.metrics_log_observer import MetricsLogObserver
from pipecat.observers.startup_timing_observer import StartupTimingObserver
from pipecat.observers.turn_tracking_observer import TurnTrackingObserver
from pipecat.observers.user_bot_latency_observer import UserBotLatencyObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor

from runtime.observers import RuntimePersistenceObserver
from runtime.transport import SessionMessageRouter, SessionTransportAdapter
from session.context import SessionContext


@dataclass
class PipelineResources:
    task: PipelineTask
    context: LLMContext


def build_pipeline_task(
    *,
    session_context: SessionContext,
    transport_adapter: SessionTransportAdapter,
    router: SessionMessageRouter,
    stt_service,
    llm_service,
    tts_service,
    persistence_observer: RuntimePersistenceObserver,
) -> PipelineResources:
    message_history = [
        {"role": "system", "content": session_context.start_payload.conversation.system_prompt},
        *session_context.start_payload.conversation.initial_messages,
    ]
    context = LLMContext(message_history)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(context)
    audio_buffer = AudioBufferProcessor(
        sample_rate=session_context.start_payload.media.sample_rate,
        num_channels=session_context.start_payload.media.channels,
    )

    pipeline = Pipeline(
        [
            transport_adapter.transport.input(),
            router,
            stt_service,
            user_aggregator,
            llm_service,
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
    return PipelineResources(task=task, context=context)
