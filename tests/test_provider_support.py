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
            "llm": {"provider": "reference", "model": "reference-v1"},
            "tts": {"provider": "cartesia", "voice": "voice-id-1", "language": "zh-CN"},
        }
    )
    resolved = router.resolve(selection)
    assert resolved.asr_provider == "deepgram"
    assert resolved.asr_options["language"] == "en"
    assert resolved.tts_provider == "cartesia"
    assert resolved.tts_options["language"] == "zh-CN"


def test_factory_supports_deepgram_and_cartesia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-deepgram-key")
    monkeypatch.setenv("CARTESIA_API_KEY", "test-cartesia-key")
    monkeypatch.setenv("CARTESIA_VOICE_ID", "11111111-1111-1111-1111-111111111111")

    router = ProviderRouter()
    selection = ProviderSelection.model_validate(
        {
            "asr": {"provider": "deepgram", "model": "nova-3-general", "language": "en"},
            "llm": {"provider": "reference", "model": "reference-v1"},
            "tts": {"provider": "cartesia", "model": "sonic-3"},
        }
    )
    resolved = router.resolve(selection)
    asr, llm, tts = PipecatServiceFactory().create_services(
        providers=resolved,
        text_supplier=lambda: "hello",
    )
    assert type(asr).__name__ == "DeepgramSTTService"
    assert type(llm).__name__ == "ReferenceLLMProcessor"
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
        text_supplier=lambda: "hello",
    )
    assert type(asr).__name__ == "DeepgramSTTService"
    assert type(llm).__name__ == "OpenAILLMService"
    assert type(tts).__name__ == "CartesiaTTSService"


def test_factory_deepgram_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    router = ProviderRouter()
    selection = ProviderSelection.model_validate(
        {
            "asr": {"provider": "deepgram", "model": "nova-3-general"},
            "llm": {"provider": "reference", "model": "reference-v1"},
            "tts": {"provider": "reference", "model": "reference-v1"},
        }
    )
    resolved = router.resolve(selection)
    with pytest.raises(UnsupportedProviderError):
        PipecatServiceFactory().create_services(providers=resolved, text_supplier=lambda: "hello")


def test_factory_openrouter_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    router = ProviderRouter()
    selection = ProviderSelection.model_validate(
        {
            "asr": {"provider": "reference", "model": "reference-v1"},
            "llm": {"provider": "openrouter", "model": "openai/gpt-4.1-mini"},
            "tts": {"provider": "reference", "model": "reference-v1"},
        }
    )
    resolved = router.resolve(selection)
    with pytest.raises(UnsupportedProviderError):
        PipecatServiceFactory().create_services(providers=resolved, text_supplier=lambda: "hello")
