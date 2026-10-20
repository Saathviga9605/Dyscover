"""Whisper model management and Hugging Face provider integration."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from transformers import WhisperForConditionalGeneration, WhisperProcessor

logger = logging.getLogger(__name__)


@dataclass
class WhisperModelConfig:
    model_name_or_path: str = "openai/whisper-tiny"
    language: str = "en"
    task: str = "transcribe"
    device: str = "auto"
    torch_dtype: str = "float32"
    local_files_only: bool = False
    cache_dir: str | None = None


class WhisperModelManager:
    """Manages Whisper model loading, device placement, and inference."""

    def __init__(self, config: WhisperModelConfig | None = None):
        self.config = config or WhisperModelConfig()
        self._model: WhisperForConditionalGeneration | None = None
        self._processor: WhisperProcessor | None = None
        self._device: torch.device | None = None
        self._loaded = False

    @property
    def device(self) -> torch.device:
        if self._device is None:
            self._device = self._resolve_device()
        return self._device

    def _resolve_device(self) -> torch.device:
        if self.config.device == "auto":
            if torch.cuda.is_available():
                return torch.device("cuda")
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return torch.device("mps")
            return torch.device("cpu")
        return torch.device(self.config.device)

    @property
    def torch_dtype(self) -> torch.dtype:
        return {
            "float32": torch.float32,
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
        }.get(self.config.torch_dtype, torch.float32)

    def load(self) -> tuple[WhisperForConditionalGeneration, WhisperProcessor]:
        """Load model and processor. Returns cached instances if already loaded."""
        if self._loaded and self._model is not None and self._processor is not None:
            return self._model, self._processor

        logger.info(f"Loading Whisper model: {self.config.model_name_or_path} on {self.device}")

        try:
            self._processor = WhisperProcessor.from_pretrained(
                self.config.model_name_or_path,
                language=self.config.language,
                task=self.config.task,
                local_files_only=self.config.local_files_only,
                cache_dir=self.config.cache_dir,
            )

            self._model = WhisperForConditionalGeneration.from_pretrained(
                self.config.model_name_or_path,
                torch_dtype=self.torch_dtype,
                local_files_only=self.config.local_files_only,
                cache_dir=self.config.cache_dir,
            )

            self._model.to(self.device)
            self._model.eval()

            self._loaded = True
            logger.info("Whisper model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise RuntimeError(f"Could not load Whisper model: {e}") from e

        return self._model, self._processor

    def unload(self) -> None:
        """Unload model to free memory."""
        self._model = None
        self._processor = None
        self._loaded = False
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def transcribe(
        self,
        audio_array: torch.Tensor | "np.ndarray",
        language: str | None = None,
        task: str | None = None,
        generate_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Transcribe audio array using loaded model."""
        import numpy as np

        if not self._loaded:
            self.load()

        model, processor = self._model, self._processor
        assert model is not None and processor is not None

        # Convert to numpy if tensor
        if isinstance(audio_array, torch.Tensor):
            audio_array = audio_array.cpu().numpy()

        # Ensure correct shape
        if audio_array.ndim > 1:
            audio_array = audio_array.squeeze()

        # Process audio
        inputs = processor(
            audio_array,
            sampling_rate=16000,
            return_tensors="pt",
        ).to(self.device)

        # Generate
        gen_kwargs = generate_kwargs or {}
        gen_kwargs.setdefault("max_length", 448)
        gen_kwargs.setdefault("num_beams", 5)

        if language:
            gen_kwargs["language"] = language
        if task:
            gen_kwargs["task"] = task

        with torch.no_grad():
            predicted_ids = model.generate(inputs.input_features, **gen_kwargs)

        # Decode
        transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]

        return {
            "text": transcription.strip(),
            "language": language or self.config.language,
            "task": task or self.config.task,
        }

    def transcribe_with_timestamps(
        self,
        audio_array: torch.Tensor | "np.ndarray",
        language: str | None = None,
        task: str | None = None,
        generate_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Transcribe with word-level timestamps (requires newer transformers)."""
        import numpy as np

        if not self._loaded:
            self.load()

        model, processor = self._model, self._processor
        assert model is not None and processor is not None

        if isinstance(audio_array, torch.Tensor):
            audio_array = audio_array.cpu().numpy()
        if audio_array.ndim > 1:
            audio_array = audio_array.squeeze()

        inputs = processor(
            audio_array,
            sampling_rate=16000,
            return_tensors="pt",
        ).to(self.device)

        gen_kwargs = generate_kwargs or {}
        gen_kwargs.setdefault("max_length", 448)
        gen_kwargs.setdefault("num_beams", 5)
        gen_kwargs.setdefault("return_timestamps", True)

        if language:
            gen_kwargs["language"] = language
        if task:
            gen_kwargs["task"] = task

        with torch.no_grad():
            outputs = model.generate(inputs.input_features, **gen_kwargs)

        # Decode with timestamps
        result = processor.batch_decode(outputs, skip_special_tokens=True, decode_with_timestamps=True)[0]

        return {
            "text": result,
            "language": language or self.config.language,
            "task": task or self.config.task,
        }

    def get_model_info(self) -> dict[str, Any]:
        """Get model metadata."""
        return {
            "model_name_or_path": self.config.model_name_or_path,
            "language": self.config.language,
            "task": self.config.task,
            "device": str(self.device),
            "torch_dtype": str(self.torch_dtype),
            "loaded": self._loaded,
            "num_parameters": sum(p.numel() for p in self._model.parameters()) if self._model else 0,
        }


class HuggingFaceWhisperProvider:
    """Hugging Face Whisper provider compatible with Dyscover's SpeechProvider interface."""

    name = "huggingface-whisper"

    def __init__(
        self,
        model_name_or_path: str = "openai/whisper-tiny",
        language: str = "en",
        device: str = "auto",
        torch_dtype: str = "float32",
        cache_dir: str | None = None,
    ):
        self.model_name_or_path = model_name_or_path
        self.language = language
        self.device = device
        self.torch_dtype = torch_dtype
        self.cache_dir = cache_dir
        self._manager: WhisperModelManager | None = None
        self.version = "unloaded"

    def _get_manager(self) -> WhisperModelManager:
        if self._manager is None:
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

    def health_check(self) -> str:
        """Return provider health status."""
        try:
            if not self.model_name_or_path:
                return "NOT_CONFIGURED"
            # Don't load model for health check, just verify path exists if local
            if Path(self.model_name_or_path).exists() or "/" not in self.model_name_or_path:
                return "AVAILABLE"
            return "NOT_CONFIGURED"
        except Exception:
            return "UNAVAILABLE"

    def transcribe(self, audio_path: Path, language: str | None = None) -> dict[str, Any]:
        """Transcribe audio file."""
        from .audio import AudioPreprocessor, AudioConfig

        preprocessor = AudioPreprocessor(AudioConfig())
        audio_array = preprocessor.preprocess_for_whisper(audio_path)

        manager = self._get_manager()
        self.version = manager.config.model_name_or_path
        result = manager.transcribe(audio_array, language=language or self.language)

        return {
            "text": result["text"],
            "language": result["language"],
            "provider": self.name,
            "provider_version": self.version,
        }

    def transcribe_array(
        self,
        audio_array: torch.Tensor | "np.ndarray",
        language: str | None = None,
    ) -> dict[str, Any]:
        """Transcribe preprocessed audio array."""
        manager = self._get_manager()
        self.version = manager.config.model_name_or_path
        result = manager.transcribe(audio_array, language=language or self.language)
        return {
            "text": result["text"],
            "language": result["language"],
            "provider": self.name,
            "provider_version": self.version,
        }

    def metadata(self) -> dict[str, Any]:
        manager = self._get_manager()
        info = manager.get_model_info()
        return {
            "provider": self.name,
            "provider_version": self.version,
            "state": self.health_check(),
            "model_info": info,
        }