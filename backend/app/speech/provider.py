from abc import ABC, abstractmethod
from typing import Any

from .schemas import ProviderState, Transcript


class SpeechProvider(ABC):
    name = "unconfigured"
    version = "unknown"

    @abstractmethod
    def transcribe(self, audio_reference: str) -> Transcript:
        raise NotImplementedError

    def health_check(self) -> ProviderState:
        return ProviderState.NOT_CONFIGURED

    def metadata(self) -> dict[str, Any]:
        return {"provider": self.name, "provider_version": self.version, "state": self.health_check().value}


class UnconfiguredSpeechProvider(SpeechProvider):
    def transcribe(self, audio_reference: str) -> Transcript:
        raise RuntimeError("No speech provider is configured; raw audio is not processed.")

    def health_check(self) -> ProviderState:
        return ProviderState.NOT_CONFIGURED


def get_speech_provider() -> SpeechProvider:
    return UnconfiguredSpeechProvider()
