"""Provider 选路标准化。

输入是北向 payload，输出是运行时稳定可用的 ResolvedProviders。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from schemas.provider import ProviderSelection


@dataclass(frozen=True)
class ResolvedProviders:
    """运行时已解析的 provider 组合。"""
    asr_provider: str
    asr_model: str | None
    asr_options: dict[str, Any]
    llm_provider: str
    llm_model: str | None
    llm_options: dict[str, Any]
    tts_provider: str
    tts_model: str | None
    tts_voice: str | None
    tts_options: dict[str, Any]


class ProviderRouter:
    """Normalize provider selection payload into an immutable resolved object."""

    @staticmethod
    def _options_from_config(config) -> dict[str, Any]:
        return config.model_dump(mode="json")

    def resolve(self, selection: ProviderSelection) -> ResolvedProviders:
        """把请求里的 provider 配置转成统一结构。"""
        return ResolvedProviders(
            asr_provider=selection.asr.provider,
            asr_model=selection.asr.model,
            asr_options=self._options_from_config(selection.asr),
            llm_provider=selection.llm.provider,
            llm_model=selection.llm.model,
            llm_options=self._options_from_config(selection.llm),
            tts_provider=selection.tts.provider,
            tts_model=selection.tts.model,
            tts_voice=selection.tts.voice,
            tts_options=self._options_from_config(selection.tts),
        )
