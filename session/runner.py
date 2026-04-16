"""单会话执行器。

负责把一个 WebSocket 会话完整走完：启动、运行、收口、落库。
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import WebSocket
from loguru import logger
from pipecat.frames.frames import EndFrame, LLMRunFrame, StartInterruptionFrame, TTSSpeakFrame
from pipecat.pipeline.runner import PipelineRunner
from pipecat.processors.aggregators.llm_response_universal import AssistantTurnStoppedMessage, UserTurnStoppedMessage
from starlette.websockets import WebSocketState

from gateway.protocol import json_payload, utc_now_iso
from providers.factory import PipecatServiceFactory, UnsupportedProviderError
from providers.router import ProviderRouter
from runtime.metrics import RuntimeMetricsCollector
from runtime.observers import RuntimePersistenceObserver
from runtime.pipeline_factory import build_pipeline_task
from runtime.processors import SilenceDetector
from runtime.transport import SessionMessageRouter, SessionTransportAdapter
from schemas.event import EventType
from schemas.messages import (
    SessionFailedMessage,
    SessionFailedPayload,
    SessionFinalizedMessage,
    SessionFinalizedPayload,
    SessionReadyMessage,
    SessionReadyPayload,
    SessionStartMessage,
)
from schemas.session import SessionStatus, TerminationCode
from session.context import SessionContext
from session.registry import SessionRegistry
from session.state_machine import SessionStateMachine
from storage.finalizer import Finalizer
from storage.repositories import Repositories, create_repositories


registry = SessionRegistry()

USER_TURN_STARTED_EVENT = "turn.user.started"
USER_TURN_STOPPED_EVENT = "turn.user.stopped"
USER_TURN_STOP_TIMEOUT_EVENT = "turn.user.stop_timeout"
ASSISTANT_TURN_STOPPED_EVENT = "turn.assistant.stopped"
USER_EMERGENCY_INTERRUPT_EVENT = "turn.user.emergency_interrupt"


def build_no_response_follow_up(language: str) -> str:
    """Default short follow-up message used while waiting for the user."""
    lang_code = language.split("-")[0].lower() if language else "zh"
    if lang_code == "en":
        return "Hi, are you still there?"
    if lang_code == "es":
        return "Hola, sigues ahi?"
    return "您好，还在听吗？"


def build_no_response_hangup_prompt(language: str) -> str:
    """Ask the model to end the call naturally after repeated silence."""
    lang_code = language.split("-")[0].lower() if language else "zh"
    if lang_code == "en":
        return (
            "The user has not responded after repeated follow-ups. "
            "Say one short closing sentence that checks if they are still there, "
            "then politely end the call. The final word must be exactly 'goodbye'."
        )
    if lang_code == "es":
        return (
            "El usuario no ha respondido despues de varios intentos. "
            "Di una sola frase breve para confirmar si sigue ahi y luego cierra la llamada "
            "con cortesía. La ultima palabra debe ser exactamente 'chao'."
        )
    return (
        "用户在多次追问后仍未回应。"
        "请只说一句简短的话，先确认对方是否还在线，再礼貌结束通话。"
        "最后两个字必须是“再见”。"
    )


@dataclass
class RuntimeResources:
    """Runtime-scoped objects shared during one websocket session."""
    session_context: SessionContext
    state_machine: SessionStateMachine
    repositories: Repositories
    metrics: RuntimeMetricsCollector
    finalizer: Finalizer


def create_runtime_context(websocket: WebSocket, start_message: SessionStartMessage) -> RuntimeResources:
    """Allocate per-session context + infra handles used by run_session()."""
    session_context = SessionContext(
        session_id=f"sess_{uuid4().hex}",
        trace_id=f"trace_{uuid4().hex}",
        websocket=websocket,
        start_payload=start_message.payload,
        metadata={
            **start_message.payload.metadata.model_dump(mode="json"),
            "request_id": start_message.request_id,
        },
    )
    repositories = create_repositories()
    return RuntimeResources(
        session_context=session_context,
        state_machine=SessionStateMachine(),
        repositories=repositories,
        metrics=RuntimeMetricsCollector(),
        finalizer=Finalizer(repositories),
    )


def create_services(start_message: SessionStartMessage, metrics: RuntimeMetricsCollector):
    """Resolve provider config from session.start and build Pipecat services."""
    provider_router = ProviderRouter()
    resolved = provider_router.resolve(start_message.payload.providers)
    metrics.register_provider("asr", resolved.asr_provider, resolved.asr_model)
    metrics.register_provider("llm", resolved.llm_provider, resolved.llm_model)
    metrics.register_provider("tts", resolved.tts_provider, resolved.tts_model or resolved.tts_voice)
    factory = PipecatServiceFactory()
    stt_service, llm_service, tts_service = factory.create_services(
        providers=resolved,
    )
    return resolved, stt_service, llm_service, tts_service


def create_transport(websocket: WebSocket) -> SessionTransportAdapter:
    """Create WS <-> Pipecat transport adapter."""
    return SessionTransportAdapter.create(websocket)


async def finalize_session(resources: RuntimeResources) -> SessionFinalizedMessage:
    """Flush final aggregates to DB and produce northbound session.finalized."""
    await resources.finalizer.finalize(
        session_context=resources.session_context,
        metrics=resources.metrics,
    )
    finalized = SessionFinalizedMessage(
        session_id=resources.session_context.session_id,
        trace_id=resources.session_context.trace_id,
        timestamp=utc_now_iso(),
        payload=SessionFinalizedPayload(
            status=resources.session_context.status,
            termination_code=resources.session_context.termination_code or TerminationCode.NORMAL_END,
            turn_count=len(resources.metrics.turns),
            total_duration_ms=max(
                0,
                int(
                    (
                        (resources.session_context.ended_at or datetime.now(UTC))
                        - resources.session_context.created_at
                    ).total_seconds()
                    * 1000
                ),
            ),
            metadata=resources.session_context.metadata,
        ),
    )
    await resources.repositories.events.append(
        session_id=resources.session_context.session_id,
        sequence=resources.session_context.next_sequence(),
        event_type=EventType.SESSION_FINALIZED.value,
        source="finalizer",
        payload=finalized.payload.model_dump(mode="json"),
    )
    return finalized


async def run_session(websocket: WebSocket, start_message: SessionStartMessage) -> None:
    """Main lifecycle: init -> run pipeline -> finalize/failed -> cleanup."""
    resources = create_runtime_context(websocket, start_message)
    session_context = resources.session_context
    await registry.add(session_context)
    await resources.repositories.events.append(
        session_id=session_context.session_id,
        sequence=session_context.next_sequence(),
        event_type=EventType.SESSION_CREATED.value,
        source="gateway",
        payload={
            "trace_id": session_context.trace_id,
            "request_id": start_message.request_id,
        },
    )

    task = None
    runner_task = None
    max_duration_task = None
    force_silence_hangup_task = None

    async def request_stop(reason: str) -> None:
        # Idempotent close gate: ignore repeated stop requests after terminal transitions.
        if session_context.status in {SessionStatus.HANGING_UP, SessionStatus.ENDED, SessionStatus.FAILED}:
            logger.info(
                "request_stop ignored: reason={} status={} termination_code={} session_id={}",
                reason,
                session_context.status,
                session_context.termination_code,
                session_context.session_id,
            )
            return
        logger.info(
            "request_stop accepted: reason={} status_before={} termination_code_before={} session_id={}",
            reason,
            session_context.status,
            session_context.termination_code,
            session_context.session_id,
        )
        # Normalize free-form stop reasons into stable termination codes.
        if reason == TerminationCode.SILENCE_TIMEOUT.value:
            session_context.termination_code = TerminationCode.SILENCE_TIMEOUT
        elif reason == TerminationCode.MAX_DURATION_REACHED.value:
            session_context.termination_code = TerminationCode.MAX_DURATION_REACHED
        elif reason == TerminationCode.RUNTIME_ERROR.value:
            session_context.termination_code = TerminationCode.RUNTIME_ERROR
        elif reason == TerminationCode.CLIENT_DISCONNECTED.value:
            session_context.termination_code = TerminationCode.CLIENT_DISCONNECTED
        else:
            session_context.termination_code = TerminationCode.UPSTREAM_STOPPED
        try:
            resources.state_machine.transition(SessionStatus.HANGING_UP)
        except Exception:
            pass
        session_context.status = SessionStatus.HANGING_UP
        session_context.ended_at = datetime.now(UTC)
        logger.info(
            "request_stop transitioned session: reason={} status_after={} termination_code_after={} session_id={}",
            reason,
            session_context.status,
            session_context.termination_code,
            session_context.session_id,
        )
        await resources.repositories.events.append(
            session_id=session_context.session_id,
            sequence=session_context.next_sequence(),
            event_type=EventType.SESSION_ENDED.value,
            source="session_runner",
            payload={"reason": reason},
        )
        if task:
            await task.queue_frame(EndFrame(reason=reason))

    async def close_websocket_if_open(*, code: int, reason: str = "") -> None:
        """Best-effort websocket close once runtime reaches terminal state."""
        if websocket.client_state == WebSocketState.CONNECTED:
            with contextlib.suppress(Exception):
                await websocket.close(code=code, reason=reason)

    async def on_input_activity(byte_count: int) -> None:
        # Feed traffic metrics; no-response policy is handled by SilenceDetector.
        resources.metrics.input_audio_bytes += byte_count

    async def request_interrupt(payload: dict[str, Any] | None = None) -> None:
        details = payload or {}
        if session_context.status != SessionStatus.ACTIVE or not task:
            logger.info(
                "request_interrupt ignored: status={} task_present={} session_id={} payload={}",
                session_context.status,
                bool(task),
                session_context.session_id,
                details,
            )
            return
        logger.info("request_interrupt accepted: session_id={} payload={}", session_context.session_id, details)
        await resources.repositories.events.append(
            session_id=session_context.session_id,
            sequence=session_context.next_sequence(),
            event_type=USER_EMERGENCY_INTERRUPT_EVENT,
            source="interrupt",
            payload=details,
        )
        await task.queue_frame(StartInterruptionFrame())

    transport_adapter = create_transport(websocket)
    router = SessionMessageRouter(
        stop_handler=request_stop,
        input_activity_handler=on_input_activity,
    )

    if hasattr(transport_adapter.transport, "event_handler"):
        @transport_adapter.transport.event_handler("on_client_disconnected")
        async def _on_client_disconnected(_, __) -> None:
            await request_stop(TerminationCode.CLIENT_DISCONNECTED.value)

        @transport_adapter.transport.event_handler("on_session_timeout")
        async def _on_session_timeout(_, __) -> None:
            await request_stop(TerminationCode.RUNTIME_ERROR.value)

    try:
        resolved, stt_service, llm_service, tts_service = create_services(start_message, resources.metrics)
        ready_event = asyncio.Event()
        observer = RuntimePersistenceObserver(
            session_id=session_context.session_id,
            repositories=resources.repositories,
            metrics_collector=resources.metrics,
            ready_event=ready_event,
        )
        silence_detector = SilenceDetector(
            post_bot_grace_ms=start_message.payload.runtime.post_bot_grace_ms,
            user_response_timeout_ms=start_message.payload.runtime.user_response_timeout_ms,
            max_silence_follow_ups=start_message.payload.runtime.max_silence_follow_ups,
        )
        logger.info(
            "Session runtime config: barge_in={} post_bot_grace_ms={} user_response_timeout_ms={} max_silence_follow_ups={} max_session_duration_ms={} session_id={}",
            start_message.payload.runtime.barge_in,
            start_message.payload.runtime.post_bot_grace_ms,
            start_message.payload.runtime.user_response_timeout_ms,
            start_message.payload.runtime.max_silence_follow_ups,
            start_message.payload.runtime.max_session_duration_ms,
            session_context.session_id,
        )
        pipeline_resources = build_pipeline_task(
            session_context=session_context,
            transport_adapter=transport_adapter,
            router=router,
            silence_detector=silence_detector,
            stt_service=stt_service,
            llm_service=llm_service,
            tts_service=tts_service,
            persistence_observer=observer,
            interrupt_handler=request_interrupt,
        )
        task = pipeline_resources.task
        runner = PipelineRunner(handle_sigint=False)

        @pipeline_resources.user_aggregator.event_handler("on_user_turn_started")
        async def _on_user_turn_started(_, strategy) -> None:
            strategy_name = strategy.__class__.__name__
            logger.info(
                "Turn event: on_user_turn_started strategy={} session_id={}",
                strategy_name,
                session_context.session_id,
            )
            await resources.repositories.events.append(
                session_id=session_context.session_id,
                sequence=session_context.next_sequence(),
                event_type=USER_TURN_STARTED_EVENT,
                source="turn_logger",
                payload={"strategy": strategy_name},
            )

        @pipeline_resources.user_aggregator.event_handler("on_user_turn_stopped")
        async def _on_user_turn_stopped(_, strategy, message: UserTurnStoppedMessage) -> None:
            strategy_name = strategy.__class__.__name__
            logger.info(
                "Turn event: on_user_turn_stopped strategy={} transcript={!r} session_id={}",
                strategy_name,
                message.content,
                session_context.session_id,
            )
            await resources.repositories.events.append(
                session_id=session_context.session_id,
                sequence=session_context.next_sequence(),
                event_type=USER_TURN_STOPPED_EVENT,
                source="turn_logger",
                payload={
                    "strategy": strategy_name,
                    "transcript": message.content,
                    "timestamp": message.timestamp,
                    "user_id": message.user_id,
                },
            )

        @pipeline_resources.user_aggregator.event_handler("on_user_turn_stop_timeout")
        async def _on_user_turn_stop_timeout(_) -> None:
            logger.info("Turn event: on_user_turn_stop_timeout session_id={}", session_context.session_id)
            await resources.repositories.events.append(
                session_id=session_context.session_id,
                sequence=session_context.next_sequence(),
                event_type=USER_TURN_STOP_TIMEOUT_EVENT,
                source="turn_logger",
                payload=None,
            )

        @pipeline_resources.assistant_aggregator.event_handler("on_assistant_turn_stopped")
        async def _on_assistant_turn_stopped(_, message: AssistantTurnStoppedMessage) -> None:
            logger.info(
                "Turn event: on_assistant_turn_stopped transcript={!r} session_id={}",
                message.content,
                session_context.session_id,
            )
            await resources.repositories.events.append(
                session_id=session_context.session_id,
                sequence=session_context.next_sequence(),
                event_type=ASSISTANT_TURN_STOPPED_EVENT,
                source="turn_logger",
                payload={"transcript": message.content, "timestamp": message.timestamp},
            )

        async def max_duration_guard() -> None:
            # Hard cap: always terminate after max_session_duration_ms.
            await asyncio.sleep(start_message.payload.runtime.max_session_duration_ms / 1000)
            await request_stop(TerminationCode.MAX_DURATION_REACHED.value)

        @silence_detector.event_handler("on_silence_detected")
        async def _on_silence_detected(_, silence_count: int) -> None:
            nonlocal force_silence_hangup_task
            logger.info(
                "Silence event received: round={} session_status={} task_present={} session_id={}",
                silence_count,
                session_context.status,
                bool(task),
                session_context.session_id,
            )
            if session_context.status != SessionStatus.ACTIVE or not task:
                return

            language = start_message.payload.conversation.language
            max_count = silence_detector.max_silence_follow_ups
            logger.info(
                "No-response detected: round={}, max={}, session_id={}",
                silence_count,
                max_count,
                session_context.session_id,
            )
            if silence_count >= max_count:
                session_context.termination_code = TerminationCode.SILENCE_TIMEOUT
                await silence_detector.disable()
                pipeline_resources.context.add_message(
                    {
                        "role": "system",
                        "content": build_no_response_hangup_prompt(language),
                    }
                )
                await task.queue_frame(LLMRunFrame())

                async def _force_hangup_if_needed() -> None:
                    await asyncio.sleep(8)
                    if session_context.status == SessionStatus.ACTIVE:
                        await request_stop(TerminationCode.SILENCE_TIMEOUT.value)

                if force_silence_hangup_task and not force_silence_hangup_task.done():
                    force_silence_hangup_task.cancel()
                force_silence_hangup_task = asyncio.create_task(_force_hangup_if_needed())
                return

            follow_up_message = build_no_response_follow_up(language)
            logger.info(
                "No-response follow-up queued: round={}, max={}, message={!r}",
                silence_count,
                max_count,
                follow_up_message,
            )
            await task.queue_frame(TTSSpeakFrame(follow_up_message, append_to_context=False))

        @pipeline_resources.hangup_sanitizer.event_handler("on_hangup_started")
        async def _on_hangup_started(_) -> None:
            logger.info(
                "Hangup started; disabling silence detector and moving session to HANGING_UP session_id={}",
                session_context.session_id,
            )
            if session_context.status != SessionStatus.ACTIVE:
                return
            await silence_detector.disable()
            try:
                resources.state_machine.transition(SessionStatus.HANGING_UP)
            except Exception:
                pass
            session_context.status = SessionStatus.HANGING_UP
            session_context.termination_code = session_context.termination_code or TerminationCode.NORMAL_END

        runner_task = asyncio.create_task(runner.run(task))
        max_duration_task = asyncio.create_task(max_duration_guard())
        await ready_event.wait()

        # READY means transport + providers + pipeline are fully initialized.
        resources.state_machine.transition(SessionStatus.READY)
        session_context.status = SessionStatus.READY
        session_context.ready_at = datetime.now(UTC)
        ready_message = SessionReadyMessage(
            session_id=session_context.session_id,
            trace_id=session_context.trace_id,
            timestamp=utc_now_iso(),
            payload=SessionReadyPayload(media=session_context.start_payload.media),
        )
        await websocket.send_json(json_payload(ready_message))
        await resources.repositories.events.append(
            session_id=session_context.session_id,
            sequence=session_context.next_sequence(),
            event_type=EventType.SESSION_READY.value,
            source="session_runner",
            payload=ready_message.payload.model_dump(mode="json"),
        )

        resources.state_machine.transition(SessionStatus.ACTIVE)
        session_context.status = SessionStatus.ACTIVE
        session_context.active_at = datetime.now(UTC)
        await resources.repositories.events.append(
            session_id=session_context.session_id,
            sequence=session_context.next_sequence(),
            event_type=EventType.RUNTIME_STARTED.value,
            source="runtime",
            payload={
                "asr_provider": resolved.asr_provider,
                "llm_provider": resolved.llm_provider,
                "tts_provider": resolved.tts_provider,
            },
        )
        await task.queue_frame(LLMRunFrame())
        await runner_task

        # Serializer tracks raw audio bytes; copy values for final metrics aggregation.
        resources.metrics.input_audio_bytes = transport_adapter.serializer.input_audio_bytes
        resources.metrics.output_audio_bytes = transport_adapter.serializer.output_audio_bytes

        if session_context.status != SessionStatus.FAILED:
            if session_context.status != SessionStatus.HANGING_UP:
                resources.state_machine.transition(SessionStatus.HANGING_UP)
                session_context.status = SessionStatus.HANGING_UP
                session_context.termination_code = session_context.termination_code or TerminationCode.NORMAL_END
            resources.state_machine.transition(SessionStatus.ENDED)
            session_context.status = SessionStatus.ENDED
            session_context.ended_at = session_context.ended_at or datetime.now(UTC)
            finalized = await finalize_session(resources)
            await websocket.send_json(json_payload(finalized))
            await close_websocket_if_open(code=1000, reason="session_finalized")
    except UnsupportedProviderError as exc:
        # Provider unsupported/missing secret: fail fast with provider_error.
        session_context.status = SessionStatus.FAILED
        session_context.termination_code = TerminationCode.PROVIDER_ERROR
        session_context.ended_at = datetime.now(UTC)
        await resources.repositories.events.append(
            session_id=session_context.session_id,
            sequence=session_context.next_sequence(),
            event_type=EventType.SESSION_FAILED.value,
            source="providers",
            payload={"detail": str(exc)},
        )
        await websocket.send_json(
            json_payload(
                SessionFailedMessage(
                    session_id=session_context.session_id,
                    trace_id=session_context.trace_id,
                    timestamp=utc_now_iso(),
                    payload=SessionFailedPayload(
                        termination_code=TerminationCode.PROVIDER_ERROR,
                        detail=str(exc),
                    ),
                )
            )
        )
        await close_websocket_if_open(code=1011, reason="provider_error")
    except Exception as exc:
        # Catch-all runtime error path.
        logger.exception("Session failed")
        session_context.status = SessionStatus.FAILED
        session_context.termination_code = session_context.termination_code or TerminationCode.RUNTIME_ERROR
        session_context.ended_at = datetime.now(UTC)
        await resources.repositories.events.append(
            session_id=session_context.session_id,
            sequence=session_context.next_sequence(),
            event_type=EventType.SESSION_FAILED.value,
            source="session_runner",
            payload={"detail": str(exc)},
        )
        try:
            await websocket.send_json(
                json_payload(
                    SessionFailedMessage(
                        session_id=session_context.session_id,
                        trace_id=session_context.trace_id,
                        timestamp=utc_now_iso(),
                        payload=SessionFailedPayload(
                            termination_code=session_context.termination_code,
                            detail=str(exc),
                        ),
                    )
                )
            )
        except RuntimeError:
            pass
        await close_websocket_if_open(code=1011, reason="runtime_error")
    finally:
        for pending in [max_duration_task, force_silence_hangup_task]:
            if pending and not pending.done():
                pending.cancel()
        if runner_task and not runner_task.done():
            runner_task.cancel()
            with contextlib.suppress(Exception):
                await runner_task
        await close_websocket_if_open(code=1000, reason="session_finished")
        await registry.remove(session_context.session_id)
