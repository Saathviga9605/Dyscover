from abc import ABC, abstractmethod
import os
from pathlib import Path
from typing import Any

from .schemas import ProviderState, Transcript

SUPPORTED_ASR_LANGUAGES = {"en", "ta"}


class SpeechProvider(ABC):
    name = "unconfigured"
    version = "unknown"

    @abstractmethod
    def transcribe(self, audio_reference: str, language: str = "en", consent_given: bool = False) -> Transcript:
        raise NotImplementedError

    def health_check(self) -> ProviderState:
        return ProviderState.NOT_CONFIGURED

    def metadata(self) -> dict[str, Any]:
        return {"provider": self.name, "provider_version": self.version, "state": self.health_check().value}


class UnconfiguredSpeechProvider(SpeechProvider):
    def transcribe(self, audio_reference: str, language: str = "en", consent_given: bool = False) -> Transcript:
        raise RuntimeError("No speech provider is configured; raw audio is not processed.")

    def health_check(self) -> ProviderState:
        return ProviderState.NOT_CONFIGURED


def get_speech_provider() -> SpeechProvider:
    if os.getenv("DYSCOVER_ASR_PROVIDER", "").strip().lower() == "faster-whisper":
        return FasterWhisperProvider()
    return UnconfiguredSpeechProvider()


class FasterWhisperProvider(SpeechProvider):
    """Opt-in local ASR adapter; the optional dependency is never imported at startup."""

    name = "faster-whisper"

    def __init__(self) -> None:
        self.model_name = os.getenv("DYSCOVER_ASR_MODEL", "small")
        self.model_path = os.getenv("DYSCOVER_ASR_MODEL_PATH", "").strip()
        self.device = os.getenv("DYSCOVER_ASR_DEVICE", "cpu")
        self.compute_type = os.getenv("DYSCOVER_ASR_COMPUTE_TYPE", "int8")
        self._model: Any = None
        self.version = "unavailable"

    def _model_location(self) -> str:
        return self.model_path or self.model_name

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise RuntimeError("faster-whisper is not installed") from error
        if self.model_path and not Path(self.model_path).exists():
            raise RuntimeError(f"configured ASR model path does not exist: {self.model_path}")
        self._model = WhisperModel(self._model_location(), device=self.device, compute_type=self.compute_type)
        self.version = getattr(self._model, "model_size_or_path", self.model_name)
        return self._model

    def health_check(self) -> ProviderState:
        if not os.getenv("DYSCOVER_ASR_MODEL_PATH", "").strip() and not os.getenv("DYSCOVER_ASR_MODEL", "").strip():
            return ProviderState.NOT_CONFIGURED
        if not os.getenv("DYSCOVER_ASR_ALLOW_MODEL_LOAD", "").strip().lower() == "true":
            return ProviderState.NOT_CONFIGURED
        try:
            self._load_model()
        except RuntimeError:
            return ProviderState.UNAVAILABLE
        return ProviderState.AVAILABLE

    def transcribe(self, audio_reference: str, language: str = "en", consent_given: bool = False) -> Transcript:
        if language not in SUPPORTED_ASR_LANGUAGES:
            raise ValueError(f"unsupported ASR locale: {language}")
        if not consent_given:
            raise PermissionError("explicit consent is required before processing child audio")
        audio_path = Path(audio_reference)
        if not audio_path.is_file():
            raise FileNotFoundError("audio reference does not point to a local file")
        model = self._load_model()
        try:
            segments, info = model.transcribe(str(audio_path), language=language)
            parts = []
            words = []
            for segment in segments:
                parts.append(segment.text)
                for word in getattr(segment, "words", None) or []:
                    words.append({
                        "word": word.word.strip(),
                        "start_time_ms": round(word.start * 1000),
                        "end_time_ms": round(word.end * 1000),
                    })
            text = " ".join(part.strip() for part in parts).strip()
            if not text:
                return Transcript(text="", language=language, provider=self.name, provider_version=self.version, transcript_available=False, word_timestamps_available=False, quality="WARNING")
            return Transcript(
                text=text,
                language=language,
                provider=self.name,
                provider_version=self.version,
                words=words,
                transcript_available=True,
                word_timestamps_available=bool(words),
                quality="OK",
            )
        except Exception as error:
            raise RuntimeError("configured ASR transcription failed") from error
