from __future__ import annotations

import math
import os
import struct
from collections.abc import Callable
from typing import Any

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    EndFrame,
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMRunFrame,
    MetricsFrame,
    StartFrame,
    TextFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    OutputAudioRawFrame,
)
from pipecat.metrics.metrics import LLMTokenUsage, LLMUsageMetricsData, ProcessingMetricsData, TTFBMetricsData, TTSUsageMetricsData
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService, LiveOptions
from pipecat.services.openai.base_llm import BaseOpenAILLMService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transcriptions.language import Language

from providers.router import ResolvedProviders
from settings import settings


class ReferenceSTTProcessor(FrameProcessor):
    def __init__(self, *, model_name: str | None = None) -> None:
        super().__init__(name="reference-stt")
        self._model_name = model_name or "reference-stt"

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)


class ReferenceLLMProcessor(FrameProcessor):
    def __init__(self, *, text_supplier: Callable[[], str], model_name: str | None = None) -> None:
        super().__init__(name="reference-llm")
        self._text_supplier = text_supplier
        self._model_name = model_name or "reference-llm"

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMRunFrame):
            text = self._text_supplier()
            await self.push_frame(
                MetricsFrame(
                    data=[
                        TTFBMetricsData(processor=self.name, model=self._model_name, value=0.05),
                        ProcessingMetricsData(processor=self.name, model=self._model_name, value=0.09),
                        LLMUsageMetricsData(
                            processor=self.name,
                            model=self._model_name,
                            value=LLMTokenUsage(prompt_tokens=8, completion_tokens=max(1, len(text) // 4), total_tokens=8 + max(1, len(text) // 4)),
                        ),
                    ]
                ),
                direction,
            )
            await self.push_frame(LLMFullResponseStartFrame(), direction)
            await self.push_frame(TextFrame(text=text), direction)
            await self.push_frame(LLMFullResponseEndFrame(), direction)
            return

        await self.push_frame(frame, direction)


class ReferenceTTSProcessor(FrameProcessor):
    def __init__(self, *, voice_name: str | None = None, sample_rate: int = 8000, channels: int = 1) -> None:
        super().__init__(name="reference-tts")
        self._voice_name = voice_name or "reference-voice"
        self._sample_rate = sample_rate
        self._channels = channels

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TextFrame):
            text = frame.text.strip() or settings.initial_bot_text
            await self.push_frame(
                MetricsFrame(
                    data=[
                        TTFBMetricsData(processor=self.name, model=self._voice_name, value=0.03),
                        ProcessingMetricsData(processor=self.name, model=self._voice_name, value=0.06),
                        TTSUsageMetricsData(processor=self.name, model=self._voice_name, value=len(text)),
                    ]
                ),
                direction,
            )
            await self.push_frame(BotStartedSpeakingFrame(), direction)
            await self.push_frame(
                OutputAudioRawFrame(
                    audio=self._synthesize_pcm(text),
                    sample_rate=self._sample_rate,
                    num_channels=self._channels,
                ),
                direction,
            )
            await self.push_frame(BotStoppedSpeakingFrame(), direction)
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TTSSpeakFrame):
            await self.process_frame(TextFrame(frame.text), direction)
            return

        await self.push_frame(frame, direction)

    def _synthesize_pcm(self, text: str) -> bytes:
        duration_seconds = max(0.25, min(1.8, len(text) * 0.03))
        frame_count = int(self._sample_rate * duration_seconds)
        amplitude = int(32767 * settings.output_wave_gain)
        frequency = settings.output_wave_frequency_hz
        buf = bytearray()
        for index in range(frame_count):
            sample = int(amplitude * math.sin(2 * math.pi * frequency * (index / self._sample_rate)))
            buf.extend(struct.pack("<h", sample))
        return bytes(buf)


class UnsupportedProviderError(ValueError):
    pass


class PipecatServiceFactory:
    def create_services(
        self,
        *,
        providers: ResolvedProviders,
        text_supplier: Callable[[], str],
    ) -> tuple[FrameProcessor, FrameProcessor, FrameProcessor]:
        asr = self._create_asr(
            providers.asr_provider,
            providers.asr_model,
            providers.asr_options,
        )
        llm = self._create_llm(
            providers.llm_provider,
            providers.llm_model,
            text_supplier,
            providers.llm_options,
        )
        tts = self._create_tts(
            providers.tts_provider,
            providers.tts_model,
            providers.tts_voice,
            providers.tts_options,
        )
        return asr, llm, tts

    @staticmethod
    def _option(options: dict[str, Any], *keys: str, default: Any = None) -> Any:
        for key in keys:
            value = options.get(key)
            if value is not None and value != "":
                return value
        return default

    @staticmethod
    def _required_secret(value: str | None, env_name: str, provider: str) -> str:
        if value:
            return value
        env_value = os.getenv(env_name)
        if env_value:
            return env_value
        raise UnsupportedProviderError(f"{provider} requires {env_name} or explicit api_key in provider config")

    @staticmethod
    def _to_language(raw: str | None) -> Language | None:
        if not raw:
            return None
        normalized = str(raw).strip().lower().replace("_", "-")
        candidates = [normalized]
        if "-" in normalized:
            candidates.append(normalized.split("-", 1)[0])
        for candidate in candidates:
            for member in Language:
                if member.value.lower() == candidate:
                    return member
        for member in Language:
            if member.name.lower().replace("_", "-") == normalized:
                return member
        return None

    def _create_asr(self, provider: str, model: str | None, options: dict[str, Any]) -> FrameProcessor:
        if provider == "reference":
            return ReferenceSTTProcessor(model_name=model)
        if provider == "deepgram":
            api_key = self._required_secret(
                self._option(options, "api_key", "apiKey"),
                "DEEPGRAM_API_KEY",
                provider,
            )
            live_options = LiveOptions(
                encoding=self._option(options, "encoding", default="linear16"),
                language=self._option(options, "language", default="en"),
                model=model or self._option(options, "model", default="nova-3-general"),
                channels=int(self._option(options, "channels", default=1)),
                interim_results=bool(self._option(options, "interim_results", default=True)),
                smart_format=bool(self._option(options, "smart_format", default=False)),
                punctuate=bool(self._option(options, "punctuate", default=True)),
                profanity_filter=bool(self._option(options, "profanity_filter", default=True)),
                vad_events=bool(self._option(options, "vad_events", default=False)),
            )
            sample_rate = int(
                self._option(
                    options,
                    "sample_rate",
                    default=settings.default_audio_sample_rate,
                )
            )
            base_url = self._option(options, "base_url", "url", default="")
            return DeepgramSTTService(
                api_key=api_key,
                sample_rate=sample_rate,
                live_options=live_options,
                base_url=base_url,
            )
        raise UnsupportedProviderError(f"ASR provider {provider!r} is not implemented yet")

    def _create_llm(
        self,
        provider: str,
        model: str | None,
        text_supplier: Callable[[], str],
        options: dict[str, Any],
    ) -> FrameProcessor:
        if provider == "reference":
            return ReferenceLLMProcessor(text_supplier=text_supplier, model_name=model)
        if provider in {"openai", "openrouter"}:
            return self._create_openai_compatible_llm(provider, model, options)
        raise UnsupportedProviderError(f"LLM provider {provider!r} is not implemented yet")

    def _create_tts(
        self,
        provider: str,
        model: str | None,
        voice: str | None,
        options: dict[str, Any],
    ) -> FrameProcessor:
        if provider == "reference":
            return ReferenceTTSProcessor(voice_name=voice or model)
        if provider == "cartesia":
            api_key = self._required_secret(
                self._option(options, "api_key", "apiKey"),
                "CARTESIA_API_KEY",
                provider,
            )
            voice_id = self._option(options, "voice_id", "voiceId", "voice", default=voice)
            voice_id = self._required_secret(voice_id, "CARTESIA_VOICE_ID", provider)
            sample_rate = int(
                self._option(
                    options,
                    "sample_rate",
                    default=settings.default_audio_sample_rate,
                )
            )
            language = self._to_language(self._option(options, "language"))
            params = CartesiaTTSService.InputParams(language=language) if language else None
            return CartesiaTTSService(
                api_key=api_key,
                voice_id=voice_id,
                model=model or self._option(options, "model", default="sonic-3"),
                sample_rate=sample_rate,
                encoding=self._option(options, "encoding", default="pcm_s16le"),
                container=self._option(options, "container", default="raw"),
                url=self._option(options, "url", default="wss://api.cartesia.ai/tts/websocket"),
                cartesia_version=self._option(options, "cartesia_version", default="2025-04-16"),
                params=params,
            )
        raise UnsupportedProviderError(f"TTS provider {provider!r} is not implemented yet")

    def _create_openai_compatible_llm(
        self,
        provider: str,
        model: str | None,
        options: dict[str, Any],
    ) -> FrameProcessor:
        if provider == "openrouter":
            api_key = self._required_secret(
                self._option(options, "api_key", "apiKey"),
                "OPENROUTER_API_KEY",
                provider,
            )
            base_url = self._option(
                options,
                "base_url",
                "baseUrl",
                default="https://openrouter.ai/api/v1",
            )
            model_name = model or self._option(options, "model", default="openai/gpt-4.1-mini")
            default_headers = dict(self._option(options, "headers", default={}) or {})
            referer = self._option(options, "referer", default=os.getenv("OPENROUTER_HTTP_REFERER"))
            x_title = self._option(options, "title", default=os.getenv("OPENROUTER_X_TITLE"))
            if referer:
                default_headers.setdefault("HTTP-Referer", str(referer))
            if x_title:
                default_headers.setdefault("X-Title", str(x_title))
        else:
            api_key = self._required_secret(
                self._option(options, "api_key", "apiKey"),
                "OPENAI_API_KEY",
                provider,
            )
            base_url = self._option(options, "base_url", "baseUrl", default=None)
            model_name = model or self._option(options, "model", default="gpt-4.1")
            default_headers = dict(self._option(options, "headers", default={}) or {})

        llm_params = BaseOpenAILLMService.InputParams(
            temperature=self._option(options, "temperature", default=None),
            top_p=self._option(options, "top_p", "topP", default=None),
            max_tokens=self._option(options, "max_tokens", "maxTokens", default=None),
            max_completion_tokens=self._option(
                options,
                "max_completion_tokens",
                "maxCompletionTokens",
                default=None,
            ),
            frequency_penalty=self._option(options, "frequency_penalty", "frequencyPenalty", default=None),
            presence_penalty=self._option(options, "presence_penalty", "presencePenalty", default=None),
            seed=self._option(options, "seed", default=None),
            service_tier=self._option(options, "service_tier", "serviceTier", default=None),
            extra=self._option(options, "extra", default=None),
        )

        return OpenAILLMService(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            default_headers=default_headers or None,
            organization=self._option(options, "organization", default=None),
            project=self._option(options, "project", default=None),
            params=llm_params,
        )
