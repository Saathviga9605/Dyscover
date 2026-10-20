from abc import ABC, abstractmethod
import importlib.util
import os
import threading
from pathlib import Path
from typing import Any

from .schemas import ProviderState, Transcript

SUPPORTED_ASR_LANGUAGES = {"en", "ta", "hi", "bn", "te", "mr", "gu", "kn", "ml", "pa", "or", "as"}


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


KNOWN_PROVIDERS = ("faster-whisper", "huggingface-whisper")
_provider_cache: dict[str, "SpeechProvider"] = {}
_provider_lock = threading.Lock()


def get_speech_provider(name: str | None = None) -> SpeechProvider:
    """Return the named provider (default: ``DYSCOVER_ASR_PROVIDER``).

    Instances are cached per process so a loaded model is reused across requests.
    """
    provider_name = (name if name is not None else os.getenv("DYSCOVER_ASR_PROVIDER", "")).strip().lower()
    if provider_name not in KNOWN_PROVIDERS:
        return UnconfiguredSpeechProvider()
    with _provider_lock:
        provider = _provider_cache.get(provider_name)
        if provider is None:
            provider = FasterWhisperProvider() if provider_name == "faster-whisper" else HuggingFaceWhisperProvider()
            _provider_cache[provider_name] = provider
        return provider


def reset_speech_providers() -> None:
    with _provider_lock:
        _provider_cache.clear()


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


class HuggingFaceWhisperProvider(SpeechProvider):
    """Hugging Face Transformers Whisper provider for local inference."""

    name = "huggingface-whisper"

    def __init__(self) -> None:
        self.model_name_or_path = os.getenv("DYSCOVER_HF_WHISPER_MODEL", "openai/whisper-tiny").strip()
        self.language = os.getenv("DYSCOVER_HF_WHISPER_LANGUAGE", "en").strip()
        self.device = os.getenv("DYSCOVER_HF_WHISPER_DEVICE", "auto").strip()
        self.torch_dtype = os.getenv("DYSCOVER_HF_WHISPER_DTYPE", "float32").strip()
        self.cache_dir = os.getenv("DYSCOVER_HF_WHISPER_CACHE", "").strip() or None
        self._manager = None
        self.version = "unloaded"

    def _get_manager(self):
        if self._manager is None:
            try:
                from app.ml.speech.model import WhisperModelManager, WhisperModelConfig
            except ImportError as error:
                raise RuntimeError("Speech ML dependencies not installed") from error

            config = WhisperModelConfig(
                model_name_or_path=self.model_name_or_path,
                language=self.language,
                device=self.device,
                torch_dtype=self.torch_dtype,
                cache_dir=self.cache_dir,
                local_files_only=bool(self.cache_dir and Path(self.cache_dir).exists()),
            )
            self._manager = WhisperModelManager(config)
        return self._manager

    def health_check(self) -> ProviderState:
        if not os.getenv("DYSCOVER_HF_WHISPER_MODEL", "").strip():
            return ProviderState.NOT_CONFIGURED
        if importlib.util.find_spec("transformers") is None or importlib.util.find_spec("torch") is None:
            return ProviderState.UNAVAILABLE
        if Path(self.model_name_or_path).exists():
            return ProviderState.AVAILABLE
        # A hub model ID is only usable when downloads are explicitly allowed or it is cached.
        if os.getenv("DYSCOVER_ASR_ALLOW_MODEL_LOAD", "").strip().lower() == "true":
            return ProviderState.AVAILABLE
        return ProviderState.UNAVAILABLE

    def transcribe(self, audio_reference: str, language: str = "en", consent_given: bool = False) -> Transcript:
        if language not in SUPPORTED_ASR_LANGUAGES:
            raise ValueError(f"unsupported ASR locale: {language}")
        if not consent_given:
            raise PermissionError("explicit consent is required before processing child audio")

        audio_path = Path(audio_reference)
        if not audio_path.is_file():
            raise FileNotFoundError("audio reference does not point to a local file")

        manager = self._get_manager()
        self.version = manager.config.model_name_or_path

        try:
            from app.ml.speech.audio import AudioPreprocessor, AudioConfig
            preprocessor = AudioPreprocessor(AudioConfig())
            audio_array = preprocessor.preprocess_for_whisper(audio_path)

            result = manager.transcribe(audio_array, language=language or self.language)

            return Transcript(
                text=result["text"],
                language=result["language"],
                provider=self.name,
                provider_version=self.version,
                transcript_available=bool(result["text"]),
                quality="OK" if result["text"] else "WARNING",
            )
        except Exception as error:
            raise RuntimeError("Hugging Face Whisper transcription failed") from error
