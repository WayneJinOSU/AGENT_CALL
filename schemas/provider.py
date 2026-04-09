"""Provider 配置 schema。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ProviderConfig(BaseModel):
    """单能力（asr/llm/tts）的 provider 配置。"""
    model_config = ConfigDict(extra="allow")

    provider: str
    model: str | None = None
    voice: str | None = None


class ProviderSelection(BaseModel):
    """三能力 provider 组合配置。"""
    model_config = ConfigDict(extra="ignore")

    asr: ProviderConfig
    llm: ProviderConfig
    tts: ProviderConfig
