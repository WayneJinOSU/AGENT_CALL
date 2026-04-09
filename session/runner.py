from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import WebSocket
from pipecat.frames.frames import EndFrame, LLMRunFrame
from pipecat.pipeline.runner import PipelineRunner

from gateway.protocol import json_payload, utc_now_iso
from providers.factory import PipecatServiceFactory, UnsupportedProviderError
from providers.router import ProviderRouter
from runtime.metrics import RuntimeMetricsCollector
from runtime.observers import RuntimePersistenceObserver
from runtime.pipeline_factory import build_pipeline_task
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


@dataclass
class RuntimeResources:
    session_context: SessionContext
    state_machine: SessionStateMachine
    repositories: Repositories
    metrics: RuntimeMetricsCollector
    finalizer: Finalizer


def create_runtime_context(websocket: WebSocket, start_message: SessionStartMessage) -> RuntimeResources:
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
    return SessionTransportAdapter.create(websocket)


async def finalize_session(resources: RuntimeResources) -> SessionFinalizedMessage:
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
    silence_task = None

    async def request_stop(reason: str) -> None:
        if session_context.status in {SessionStatus.HANGING_UP, SessionStatus.ENDED, SessionStatus.FAILED}:
            return
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
        await resources.repositories.events.append(
            session_id=session_context.session_id,
            sequence=session_context.next_sequence(),
            event_type=EventType.SESSION_ENDED.value,
            source="session_runner",
            payload={"reason": reason},
        )
        if task:
            await task.queue_frame(EndFrame(reason=reason))

    async def on_input_activity(byte_count: int) -> None:
        resources.metrics.input_audio_bytes += byte_count
        session_context.metadata["last_input_at"] = utc_now_iso()

    transport_adapter = create_transport(websocket)
    router = SessionMessageRouter(stop_handler=request_stop, input_activity_handler=on_input_activity)

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
        pipeline_resources = build_pipeline_task(
            session_context=session_context,
            transport_adapter=transport_adapter,
            router=router,
            stt_service=stt_service,
            llm_service=llm_service,
            tts_service=tts_service,
            persistence_observer=observer,
        )
        task = pipeline_resources.task
        runner = PipelineRunner(handle_sigint=False)

        async def max_duration_guard() -> None:
            await asyncio.sleep(start_message.payload.runtime.max_session_duration_ms / 1000)
            await request_stop(TerminationCode.MAX_DURATION_REACHED.value)

        async def silence_guard() -> None:
            timeout_seconds = start_message.payload.runtime.silence_timeout_ms / 1000
            while True:
                await asyncio.sleep(timeout_seconds)
                last_input_at_raw = session_context.metadata.get("last_input_at")
                if not last_input_at_raw:
                    if session_context.status == SessionStatus.ACTIVE:
                        await request_stop(TerminationCode.SILENCE_TIMEOUT.value)
                        return
                    continue
                last_input_at = datetime.fromisoformat(last_input_at_raw)
                idle_seconds = (datetime.now(UTC) - last_input_at).total_seconds()
                if session_context.status == SessionStatus.ACTIVE and idle_seconds >= timeout_seconds:
                    await request_stop(TerminationCode.SILENCE_TIMEOUT.value)
                    return

        runner_task = asyncio.create_task(runner.run(task))
        max_duration_task = asyncio.create_task(max_duration_guard())
        silence_task = asyncio.create_task(silence_guard())
        await ready_event.wait()

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
    except UnsupportedProviderError as exc:
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
    except Exception as exc:
        logging.exception("Session failed")
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
    finally:
        for pending in [max_duration_task, silence_task]:
            if pending and not pending.done():
                pending.cancel()
        if runner_task and not runner_task.done():
            runner_task.cancel()
            with contextlib.suppress(Exception):
                await runner_task
        await registry.remove(session_context.session_id)
