from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from schemas.provider import ProviderSelection
from settings import settings


@dataclass(frozen=True)
class ResolvedProviders:
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
    @staticmethod
    def _options_from_config(config) -> dict[str, Any]:
        return config.model_dump(mode="json")

    def resolve(self, selection: ProviderSelection) -> ResolvedProviders:
        if settings.enable_reference_fallback:
            asr_provider = selection.asr.provider or settings.reference_provider_name
            llm_provider = selection.llm.provider or settings.reference_provider_name
            tts_provider = selection.tts.provider or settings.reference_provider_name
        else:
            asr_provider = selection.asr.provider
            llm_provider = selection.llm.provider
            tts_provider = selection.tts.provider
        return ResolvedProviders(
            asr_provider=asr_provider,
            asr_model=selection.asr.model,
            asr_options=self._options_from_config(selection.asr),
            llm_provider=llm_provider,
            llm_model=selection.llm.model,
            llm_options=self._options_from_config(selection.llm),
            tts_provider=tts_provider,
            tts_model=selection.tts.model,
            tts_voice=selection.tts.voice,
            tts_options=self._options_from_config(selection.tts),
        )
