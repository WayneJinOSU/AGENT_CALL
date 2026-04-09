"""会话收口器（Finalizer）。"""

from __future__ import annotations

from datetime import UTC, datetime

from runtime.metrics import RuntimeMetricsCollector
from session.context import SessionContext
from storage.repositories import Repositories


class Finalizer:
    """负责会话结束后的聚合入库。"""

    def __init__(self, repositories: Repositories) -> None:
        self._repositories = repositories

    async def finalize(self, *, session_context: SessionContext, metrics: RuntimeMetricsCollector) -> None:
        """写入 provider 聚合指标与 session 最终记录。"""
        ended_at = session_context.ended_at or datetime.now(UTC)
        provider_rows = []
        for snapshot in metrics.provider_metrics.values():
            provider_rows.append(
                {
                    "capability": snapshot.capability,
                    "provider_name": snapshot.provider_name,
                    "model_name": snapshot.model_name,
                    "connect_attempts": snapshot.connect_attempts,
                    "reconnect_count": snapshot.reconnect_count,
                    "failover_count": snapshot.failover_count,
                    "avg_ttfb_ms": snapshot.avg_ttfb_ms,
                    "max_ttfb_ms": snapshot.max_ttfb_ms,
                    "usage_input": snapshot.usage_input,
                    "usage_output": snapshot.usage_output,
                    "cost_usd": snapshot.cost_usd,
                    "metrics_json": snapshot.metadata or None,
                }
            )
        await self._repositories.provider_metrics.replace_for_session(
            session_id=session_context.session_id,
            rows=provider_rows,
        )

        total_duration_ms = max(
            0,
            int((ended_at - session_context.created_at).total_seconds() * 1000),
        )
        await self._repositories.session_records.upsert(
            session_id=session_context.session_id,
            values={
                "trace_id": session_context.trace_id,
                "status": session_context.status.value,
                "termination_code": session_context.termination_code.value if session_context.termination_code else None,
                "session_type": session_context.start_payload.session_type,
                "language": session_context.start_payload.conversation.language,
                "audio_encoding": session_context.start_payload.media.encoding,
                "sample_rate": session_context.start_payload.media.sample_rate,
                "channels": session_context.start_payload.media.channels,
                "turn_count": len(metrics.turns),
                "total_duration_ms": total_duration_ms,
                "input_audio_bytes": metrics.input_audio_bytes,
                "output_audio_bytes": metrics.output_audio_bytes,
                "metadata_json": session_context.metadata or None,
                "created_at": session_context.created_at,
                "ready_at": session_context.ready_at,
                "active_at": session_context.active_at,
                "ended_at": ended_at,
                "finalized_at": datetime.now(UTC),
            },
        )
