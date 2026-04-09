"""init v1 schema

Revision ID: 20260408_0001
Revises:
Create Date: 2026-04-08 14:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260408_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 V1 核心 5 张业务表及索引。"""
    op.create_table(
        "session_record",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("termination_code", sa.String(length=64), nullable=True),
        sa.Column("session_type", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("audio_encoding", sa.String(length=32), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=False),
        sa.Column("channels", sa.Integer(), nullable=False),
        sa.Column("turn_count", sa.Integer(), nullable=False),
        sa.Column("total_duration_ms", sa.Integer(), nullable=False),
        sa.Column("input_audio_bytes", sa.Integer(), nullable=False),
        sa.Column("output_audio_bytes", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index("ix_session_record_trace_id", "session_record", ["trace_id"])
    op.create_index("ix_session_record_created_at", "session_record", ["created_at"])

    op.create_table(
        "event_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("turn_id", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_event_log_session_sequence", "event_log", ["session_id", "sequence"])
    op.create_index("ix_event_log_event_type_occurred_at", "event_log", ["event_type", "occurred_at"])

    op.create_table(
        "session_turn_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("turn_id", sa.String(length=64), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interrupted", sa.Boolean(), nullable=False),
        sa.Column("asr_ttfb_ms", sa.Float(), nullable=True),
        sa.Column("llm_ttfb_ms", sa.Float(), nullable=True),
        sa.Column("tts_ttfb_ms", sa.Float(), nullable=True),
        sa.Column("e2e_latency_ms", sa.Float(), nullable=True),
        sa.Column("text_chars", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "turn_id", name="uq_session_turn_metrics_session_turn"),
    )
    op.create_index("ix_session_turn_metrics_session_turn_index", "session_turn_metrics", ["session_id", "turn_index"])

    op.create_table(
        "session_provider_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("capability", sa.String(length=32), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("connect_attempts", sa.Integer(), nullable=False),
        sa.Column("reconnect_count", sa.Integer(), nullable=False),
        sa.Column("failover_count", sa.Integer(), nullable=False),
        sa.Column("avg_ttfb_ms", sa.Float(), nullable=True),
        sa.Column("max_ttfb_ms", sa.Float(), nullable=True),
        sa.Column("usage_input", sa.Integer(), nullable=False),
        sa.Column("usage_output", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_session_provider_metrics_session_capability",
        "session_provider_metrics",
        ["session_id", "capability"],
    )

    op.create_table(
        "transcript_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("turn_id", sa.String(length=64), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(length=32), nullable=False),
        sa.Column("transcript_type", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transcript_log_session_turn", "transcript_log", ["session_id", "turn_id"])
    op.create_index("ix_transcript_log_session_type", "transcript_log", ["session_id", "transcript_type"])


def downgrade() -> None:
    """回滚 V1 核心表结构。"""
    op.drop_index("ix_transcript_log_session_type", table_name="transcript_log")
    op.drop_index("ix_transcript_log_session_turn", table_name="transcript_log")
    op.drop_table("transcript_log")

    op.drop_index("ix_session_provider_metrics_session_capability", table_name="session_provider_metrics")
    op.drop_table("session_provider_metrics")

    op.drop_index("ix_session_turn_metrics_session_turn_index", table_name="session_turn_metrics")
    op.drop_table("session_turn_metrics")

    op.drop_index("ix_event_log_event_type_occurred_at", table_name="event_log")
    op.drop_index("ix_event_log_session_sequence", table_name="event_log")
    op.drop_table("event_log")

    op.drop_index("ix_session_record_created_at", table_name="session_record")
    op.drop_index("ix_session_record_trace_id", table_name="session_record")
    op.drop_table("session_record")
