"""仓储层。

对上层暴露面向业务动作的方法，隐藏 ORM 细节。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from db import SessionLocal
from storage.models import EventLog, SessionProviderMetrics, SessionRecord, SessionTurnMetrics, TranscriptLog


class EventLogRepository:
    """event_log 读写。"""

    async def append(
        self,
        *,
        session_id: str,
        sequence: int,
        event_type: str,
        source: str,
        payload: dict | None = None,
        turn_id: str | None = None,
        provider: str | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        """追加一条事件记录。"""
        async with SessionLocal() as db:
            db.add(
                EventLog(
                    event_id=f"evt_{uuid4().hex}",
                    session_id=session_id,
                    sequence=sequence,
                    event_type=event_type,
                    source=source,
                    turn_id=turn_id,
                    provider=provider,
                    payload_json=payload,
                    occurred_at=occurred_at or datetime.now(UTC),
                )
            )
            await db.commit()


class TranscriptLogRepository:
    """transcript_log 读写。"""

    async def create(
        self,
        *,
        session_id: str,
        speaker: str,
        transcript_type: str,
        text: str,
        sequence: int,
        turn_id: str | None,
        metadata: dict | None,
        confidence: float | None = None,
    ) -> None:
        """写入一条转写/文本记录。"""
        async with SessionLocal() as db:
            db.add(
                TranscriptLog(
                    session_id=session_id,
                    turn_id=turn_id,
                    sequence=sequence,
                    speaker=speaker,
                    transcript_type=transcript_type,
                    text=text,
                    confidence=confidence,
                    metadata_json=metadata,
                )
            )
            await db.commit()


class SessionTurnMetricsRepository:
    """session_turn_metrics 读写。"""

    async def upsert(
        self,
        *,
        session_id: str,
        turn_id: str,
        turn_index: int,
        speaker: str,
        started_at: datetime,
        ended_at: datetime,
        interrupted: bool,
        asr_ttfb_ms: float | None,
        llm_ttfb_ms: float | None,
        tts_ttfb_ms: float | None,
        e2e_latency_ms: float | None,
        text_chars: int,
        metadata: dict | None,
    ) -> None:
        """按 (session_id, turn_id) 幂等更新 turn 指标。"""
        async with SessionLocal() as db:
            existing = await db.scalar(
                select(SessionTurnMetrics).where(
                    SessionTurnMetrics.session_id == session_id,
                    SessionTurnMetrics.turn_id == turn_id,
                )
            )
            if existing is None:
                existing = SessionTurnMetrics(
                    session_id=session_id,
                    turn_id=turn_id,
                    turn_index=turn_index,
                    speaker=speaker,
                    started_at=started_at,
                    ended_at=ended_at,
                    interrupted=interrupted,
                    asr_ttfb_ms=asr_ttfb_ms,
                    llm_ttfb_ms=llm_ttfb_ms,
                    tts_ttfb_ms=tts_ttfb_ms,
                    e2e_latency_ms=e2e_latency_ms,
                    text_chars=text_chars,
                    metadata_json=metadata,
                )
                db.add(existing)
            else:
                existing.turn_index = turn_index
                existing.speaker = speaker
                existing.started_at = started_at
                existing.ended_at = ended_at
                existing.interrupted = interrupted
                existing.asr_ttfb_ms = asr_ttfb_ms
                existing.llm_ttfb_ms = llm_ttfb_ms
                existing.tts_ttfb_ms = tts_ttfb_ms
                existing.e2e_latency_ms = e2e_latency_ms
                existing.text_chars = text_chars
                existing.metadata_json = metadata
            await db.commit()


class SessionProviderMetricsRepository:
    """session_provider_metrics 读写。"""

    async def replace_for_session(self, *, session_id: str, rows: list[dict]) -> None:
        """会话结束时全量替换 provider 聚合结果。"""
        async with SessionLocal() as db:
            existing = await db.scalars(select(SessionProviderMetrics).where(SessionProviderMetrics.session_id == session_id))
            for row in existing.all():
                await db.delete(row)
            for row in rows:
                db.add(SessionProviderMetrics(session_id=session_id, **row))
            await db.commit()


class SessionRecordRepository:
    """session_record 读写。"""

    async def upsert(self, *, session_id: str, values: dict) -> None:
        """按 session_id 幂等写入最终会话记录。"""
        async with SessionLocal() as db:
            existing = await db.scalar(select(SessionRecord).where(SessionRecord.session_id == session_id))
            if existing is None:
                db.add(SessionRecord(session_id=session_id, **values))
            else:
                for key, value in values.items():
                    setattr(existing, key, value)
            await db.commit()


@dataclass(frozen=True)
class Repositories:
    """仓储聚合对象，便于依赖注入与传递。"""
    events: EventLogRepository
    transcripts: TranscriptLogRepository
    turn_metrics: SessionTurnMetricsRepository
    provider_metrics: SessionProviderMetricsRepository
    session_records: SessionRecordRepository


def create_repositories() -> Repositories:
    """创建一组默认仓储实例。"""
    return Repositories(
        events=EventLogRepository(),
        transcripts=TranscriptLogRepository(),
        turn_metrics=SessionTurnMetricsRepository(),
        provider_metrics=SessionProviderMetricsRepository(),
        session_records=SessionRecordRepository(),
    )
