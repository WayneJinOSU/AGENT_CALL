"""Provider 默认档案常量。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderProfile:
    """描述单个 provider 的默认模型/声线。"""
    provider: str
    model: str | None = None
    voice: str | None = None


DEEPGRAM_PROFILE = ProviderProfile(provider="deepgram", model="nova-3-general")
OPENROUTER_PROFILE = ProviderProfile(provider="openrouter", model="openai/gpt-4.1-mini")
CARTESIA_PROFILE = ProviderProfile(
    provider="cartesia",
    model="sonic-2",
    voice="bf32f849-7bc9-4b91-8c62-954588efcc30",
)
