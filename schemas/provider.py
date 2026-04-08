from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: str
    model: str | None = None
    voice: str | None = None


class ProviderSelection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    asr: ProviderConfig
    llm: ProviderConfig
    tts: ProviderConfig

