"""Provider 服务工厂。

把 `session.start.providers` 中的配置转换为 Pipecat 原生 service 实例。
"""

from __future__ import annotations

import os
from typing import Any

from pipecat.processors.frame_processor import FrameProcessor
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService, LiveOptions
from pipecat.services.openai.base_llm import BaseOpenAILLMService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transcriptions.language import Language

from providers.router import ResolvedProviders
from settings import settings


class UnsupportedProviderError(ValueError):
    """Raised when provider selection is invalid for current V1 support scope."""
    pass


class PipecatServiceFactory:
    """Factory that converts resolved provider config into concrete Pipecat services."""

    def create_services(
        self,
        *,
        providers: ResolvedProviders,
    ) -> tuple[FrameProcessor, FrameProcessor, FrameProcessor]:
        # Build three capability services in a fixed order: ASR -> LLM -> TTS.
        asr = self._create_asr(
            providers.asr_provider,
            providers.asr_model,
            providers.asr_options,
        )
        llm = self._create_llm(
            providers.llm_provider,
            providers.llm_model,
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
        """Read first non-empty option from aliases, then fallback to default."""
        for key in keys:
            value = options.get(key)
            if value is not None and value != "":
                return value
        return default

    @staticmethod
    def _required_secret_from_envs(
        value: str | None,
        env_names: tuple[str, ...],
        provider: str,
    ) -> str:
        """Resolve secret from payload first, then from allowed env variable aliases."""
        if value:
            return value
        for env_name in env_names:
            env_value = os.getenv(env_name)
            if env_value:
                return env_value
        joined = " / ".join(env_names)
        raise UnsupportedProviderError(f"{provider} requires one of [{joined}] or explicit api_key in provider config")

    @staticmethod
    def _to_language(raw: str | None) -> Language | None:
        """Map loose locale text (zh-CN / zh_cn / zh) to Pipecat Language enum."""
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
        # V1 intentionally narrows ASR provider surface for predictable integration.
        if provider != "deepgram":
            raise UnsupportedProviderError(
                f"ASR provider {provider!r} is not supported in V1. Use 'deepgram'."
            )
        api_key = self._required_secret_from_envs(
            self._option(options, "api_key", "apiKey"),
            ("DEEPGRAM_API_KEY", "ASR_API_KEY", "ARS_API_KEY"),
            provider,
        )
        live_options = LiveOptions(
            encoding=self._option(options, "encoding", default="linear16"),
            language=self._option(options, "language", default="zh"),
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

    def _create_llm(
        self,
        provider: str,
        model: str | None,
        options: dict[str, Any],
    ) -> FrameProcessor:
        # OpenRouter is wired through OpenAI-compatible service adapter.
        if provider not in {"openai", "openrouter"}:
            raise UnsupportedProviderError(
                f"LLM provider {provider!r} is not supported in V1. Use 'openrouter' or 'openai'."
            )
        return self._create_openai_compatible_llm(provider, model, options)

    def _create_tts(
        self,
        provider: str,
        model: str | None,
        voice: str | None,
        options: dict[str, Any],
    ) -> FrameProcessor:
        # V1 keeps one TTS provider to reduce runtime variability.
        if provider != "cartesia":
            raise UnsupportedProviderError(
                f"TTS provider {provider!r} is not supported in V1. Use 'cartesia'."
            )
        api_key = self._required_secret_from_envs(
            self._option(options, "api_key", "apiKey"),
            ("CARTESIA_API_KEY", "TTS_API_KEY"),
            provider,
        )
        voice_id = self._option(options, "voice_id", "voiceId", "voice", default=voice)
        voice_id = self._required_secret_from_envs(
            voice_id,
            ("CARTESIA_VOICE_ID", "TTS_VOICE_ID", "VOICE_ID"),
            provider,
        )
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
            model=model or self._option(options, "model", default="sonic-2"),
            sample_rate=sample_rate,
            encoding=self._option(options, "encoding", default="pcm_s16le"),
            container=self._option(options, "container", default="raw"),
            url=self._option(options, "url", default="wss://api.cartesia.ai/tts/websocket"),
            cartesia_version=self._option(options, "cartesia_version", default="2025-04-16"),
            params=params,
        )

    def _create_openai_compatible_llm(
        self,
        provider: str,
        model: str | None,
        options: dict[str, Any],
    ) -> FrameProcessor:
        """创建 OpenAI 协议兼容的 LLM service（openai/openrouter）。"""
        if provider == "openrouter":
            # OpenRouter-specific headers are optional but useful for attribution/routing.
            api_key = self._required_secret_from_envs(
                self._option(options, "api_key", "apiKey"),
                ("OPENROUTER_API_KEY", "LLM_API_KEY"),
                provider,
            )
            base_url = self._option(
                options,
                "base_url",
                "baseUrl",
                default=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            )
            model_name = model or self._option(
                options,
                "model",
                default=os.getenv("OPENROUTER_MODEL", os.getenv("LLM_MODEL", "openai/gpt-4.1-mini")),
            )
            default_headers = dict(self._option(options, "headers", default={}) or {})
            referer = self._option(options, "referer", default=os.getenv("OPENROUTER_HTTP_REFERER"))
            x_title = self._option(options, "title", default=os.getenv("OPENROUTER_X_TITLE"))
            if referer:
                default_headers.setdefault("HTTP-Referer", str(referer))
            if x_title:
                default_headers.setdefault("X-Title", str(x_title))
        else:
            api_key = self._required_secret_from_envs(
                self._option(options, "api_key", "apiKey"),
                ("OPENAI_API_KEY", "LLM_API_KEY"),
                provider,
            )
            base_url = self._option(options, "base_url", "baseUrl", default=None)
            model_name = model or self._option(options, "model", default=os.getenv("OPENAI_MODEL", "gpt-4.1"))
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
