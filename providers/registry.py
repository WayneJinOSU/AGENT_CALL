from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderProfile:
    provider: str
    model: str | None = None
    voice: str | None = None


REFERENCE_PROFILE = ProviderProfile(provider="reference", model="reference-v1")
