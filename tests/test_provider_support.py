from __future__ import annotations

import pytest

from providers.factory import PipecatServiceFactory, UnsupportedProviderError
from providers.router import ProviderRouter
from schemas.provider import ProviderSelection


def test_router_preserves_provider_options() -> None:
    router = ProviderRouter()
    selection = ProviderSelection.model_validate(
        {
            "asr": {"provider": "deepgram", "model": "nova-3-general", "language": "en"},
            "llm": {"provider": "openrouter", "model": "openai/gpt-4.1-mini", "temperature": 0.2},
            "tts": {"provider": "cartesia", "voice": "voice-id-1", "language": "zh-CN"},
        }
    )
    resolved = router.resolve(selection)
    assert resolved.asr_provider == "deepgram"
    assert resolved.asr_options["language"] == "en"
    assert resolved.llm_provider == "openrouter"
    assert resolved.llm_options["temperature"] == 0.2
    assert resolved.tts_provider == "cartesia"
    assert resolved.tts_options["language"] == "zh-CN"


def test_factory_supports_deepgram_and_cartesia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-deepgram-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("CARTESIA_API_KEY", "test-cartesia-key")
    monkeypatch.setenv("CARTESIA_VOICE_ID", "11111111-1111-1111-1111-111111111111")

    router = ProviderRouter()
    selection = ProviderSelection.model_validate(
        {
            "asr": {"provider": "deepgram", "model": "nova-3-general", "language": "en"},
            "llm": {"provider": "openrouter", "model": "openai/gpt-4.1-mini"},
            "tts": {"provider": "cartesia", "model": "sonic-3"},
        }
    )
    resolved = router.resolve(selection)
    asr, llm, tts = PipecatServiceFactory().create_services(
        providers=resolved,
    )
    assert type(asr).__name__ == "DeepgramSTTService"
    assert type(llm).__name__ == "OpenAILLMService"
    assert type(tts).__name__ == "CartesiaTTSService"


def test_factory_supports_openrouter_with_openai_compatible_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-deepgram-key")
    monkeypatch.setenv("CARTESIA_API_KEY", "test-cartesia-key")
    monkeypatch.setenv("CARTESIA_VOICE_ID", "11111111-1111-1111-1111-111111111111")

    router = ProviderRouter()
    selection = ProviderSelection.model_validate(
        {
            "asr": {"provider": "deepgram", "model": "nova-3-general", "language": "en"},
            "llm": {
                "provider": "openrouter",
                "model": "openai/gpt-4.1-mini",
                "temperature": 0.2,
                "referer": "https://example.com",
                "title": "AGENT_CALL",
            },
            "tts": {"provider": "cartesia", "model": "sonic-3"},
        }
    )
    resolved = router.resolve(selection)
    asr, llm, tts = PipecatServiceFactory().create_services(
        providers=resolved,
    )
    assert type(asr).__name__ == "DeepgramSTTService"
    assert type(llm).__name__ == "OpenAILLMService"
    assert type(tts).__name__ == "CartesiaTTSService"


def test_factory_supports_generic_env_key_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("CARTESIA_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("ARS_API_KEY", "generic-asr-key")
    monkeypatch.setenv("TTS_API_KEY", "generic-tts-key")
    monkeypatch.setenv("TTS_VOICE_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("LLM_API_KEY", "generic-llm-key")

    router = ProviderRouter()
    selection = ProviderSelection.model_validate(
        {
            "asr": {"provider": "deepgram", "model": "nova-3-general"},
            "llm": {"provider": "openrouter", "model": "openai/gpt-4.1-mini"},
            "tts": {"provider": "cartesia", "model": "sonic-3"},
        }
    )
    resolved = router.resolve(selection)
    asr, llm, tts = PipecatServiceFactory().create_services(
        providers=resolved,
    )
    assert type(asr).__name__ == "DeepgramSTTService"
    assert type(llm).__name__ == "OpenAILLMService"
    assert type(tts).__name__ == "CartesiaTTSService"


def test_factory_deepgram_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("CARTESIA_API_KEY", "test-cartesia-key")
    monkeypatch.setenv("CARTESIA_VOICE_ID", "11111111-1111-1111-1111-111111111111")
    router = ProviderRouter()
    selection = ProviderSelection.model_validate(
        {
            "asr": {"provider": "deepgram", "model": "nova-3-general"},
            "llm": {"provider": "openrouter", "model": "openai/gpt-4.1-mini"},
            "tts": {"provider": "cartesia", "model": "sonic-3"},
        }
    )
    resolved = router.resolve(selection)
    with pytest.raises(UnsupportedProviderError):
        PipecatServiceFactory().create_services(providers=resolved)


def test_factory_openrouter_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-deepgram-key")
    monkeypatch.setenv("CARTESIA_API_KEY", "test-cartesia-key")
    monkeypatch.setenv("CARTESIA_VOICE_ID", "11111111-1111-1111-1111-111111111111")
    router = ProviderRouter()
    selection = ProviderSelection.model_validate(
        {
            "asr": {"provider": "deepgram", "model": "nova-3-general"},
            "llm": {"provider": "openrouter", "model": "openai/gpt-4.1-mini"},
            "tts": {"provider": "cartesia", "model": "sonic-3"},
        }
    )
    resolved = router.resolve(selection)
    with pytest.raises(UnsupportedProviderError):
        PipecatServiceFactory().create_services(providers=resolved)
