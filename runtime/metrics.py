from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ProviderMetricSnapshot:
    capability: str
    provider_name: str
    model_name: str | None = None
    connect_attempts: int = 1
    reconnect_count: int = 0
    failover_count: int = 0
    ttfb_ms_samples: list[float] = field(default_factory=list)
    processing_ms_samples: list[float] = field(default_factory=list)
    usage_input: int = 0
    usage_output: int = 0
    cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def avg_ttfb_ms(self) -> float | None:
        if not self.ttfb_ms_samples:
            return None
        return sum(self.ttfb_ms_samples) / len(self.ttfb_ms_samples)

    @property
    def max_ttfb_ms(self) -> float | None:
        if not self.ttfb_ms_samples:
            return None
        return max(self.ttfb_ms_samples)


@dataclass
class TurnMetricSnapshot:
    turn_id: str
    turn_index: int
    speaker: str
    started_at: datetime
    ended_at: datetime | None = None
    interrupted: bool = False
    asr_ttfb_ms: float | None = None
    llm_ttfb_ms: float | None = None
    tts_ttfb_ms: float | None = None
    e2e_latency_ms: float | None = None
    text_chars: int = 0


@dataclass
class RuntimeMetricsCollector:
    provider_metrics: dict[str, ProviderMetricSnapshot] = field(default_factory=dict)
    turns: list[TurnMetricSnapshot] = field(default_factory=list)
    active_turn: TurnMetricSnapshot | None = None
    input_audio_bytes: int = 0
    output_audio_bytes: int = 0

    def register_provider(self, capability: str, provider_name: str, model_name: str | None = None) -> None:
        self.provider_metrics[capability] = ProviderMetricSnapshot(
            capability=capability,
            provider_name=provider_name,
            model_name=model_name,
        )

    def start_assistant_turn(self) -> TurnMetricSnapshot:
        turn = TurnMetricSnapshot(
            turn_id=f"turn_{len(self.turns) + 1}",
            turn_index=len(self.turns) + 1,
            speaker="assistant",
            started_at=datetime.now(UTC),
        )
        self.turns.append(turn)
        self.active_turn = turn
        return turn

    def finish_assistant_turn(self) -> TurnMetricSnapshot | None:
        if not self.active_turn:
            return None
        self.active_turn.ended_at = datetime.now(UTC)
        finished = self.active_turn
        self.active_turn = None
        return finished

    def record_text_chars(self, char_count: int) -> None:
        if self.active_turn:
            self.active_turn.text_chars += char_count

    def record_ttfb(self, capability: str, value_seconds: float) -> None:
        snapshot = self.provider_metrics.get(capability)
        if snapshot:
            snapshot.ttfb_ms_samples.append(value_seconds * 1000)
        if self.active_turn:
            value_ms = value_seconds * 1000
            if capability == "asr":
                self.active_turn.asr_ttfb_ms = value_ms
            elif capability == "llm":
                self.active_turn.llm_ttfb_ms = value_ms
            elif capability == "tts":
                self.active_turn.tts_ttfb_ms = value_ms

    def record_processing_time(self, capability: str, value_seconds: float) -> None:
        snapshot = self.provider_metrics.get(capability)
        if snapshot:
            snapshot.processing_ms_samples.append(value_seconds * 1000)

    def record_turn_latency(self, e2e_processing_time_ms: float) -> None:
        if self.active_turn:
            self.active_turn.e2e_latency_ms = e2e_processing_time_ms

