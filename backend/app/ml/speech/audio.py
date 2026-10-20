"""Audio preprocessing utilities for speech recognition."""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
import torch
import torchaudio

logger = logging.getLogger(__name__)


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    max_duration_seconds: float = 30.0
    min_duration_seconds: float = 0.5
    normalize: bool = True
    target_dbfs: float = -20.0
    mono: bool = True


@dataclass
class AudioInfo:
    sample_rate: int
    channels: int
    duration_seconds: float
    num_samples: int
    format: str
    subtype: str


class AudioPreprocessor:
    """Handles audio loading, resampling, normalization, and validation."""

    def __init__(self, config: AudioConfig | None = None):
        self.config = config or AudioConfig()
        self._resamplers: dict[int, torchaudio.transforms.Resample] = {}

    def get_audio_info(self, audio_path: Path) -> AudioInfo:
        """Get audio file metadata without loading full audio."""
        info = sf.info(str(audio_path))
        return AudioInfo(
            sample_rate=info.samplerate,
            channels=info.channels,
            duration_seconds=info.duration,
            num_samples=info.frames,
            format=info.format or "unknown",
            subtype=info.subtype or "unknown",
        )

    def validate_audio(self, audio_path: Path) -> list[str]:
        """Validate audio file. Returns list of error messages (empty if valid)."""
        errors = []

        if not audio_path.is_file():
            errors.append(f"Audio file not found: {audio_path}")
            return errors

        try:
            info = self.get_audio_info(audio_path)
        except Exception as e:
            errors.append(f"Failed to read audio info: {e}")
            return errors

        if info.duration_seconds < self.config.min_duration_seconds:
            errors.append(f"Audio too short: {info.duration_seconds:.2f}s < {self.config.min_duration_seconds}s")
        if info.duration_seconds > self.config.max_duration_seconds:
            errors.append(f"Audio too long: {info.duration_seconds:.2f}s > {self.config.max_duration_seconds}s")
        if info.channels <= 0:
            errors.append("Invalid channel count")
        if info.sample_rate <= 0:
            errors.append("Invalid sample rate")

        return errors

    def _get_resampler(self, orig_sr: int) -> torchaudio.transforms.Resample:
        if orig_sr not in self._resamplers:
            self._resamplers[orig_sr] = torchaudio.transforms.Resample(
                orig_freq=orig_sr,
                new_freq=self.config.sample_rate,
            )
        return self._resamplers[orig_sr]

    def load_audio(self, audio_path: Path) -> tuple[torch.Tensor, int]:
        """Load audio file as mono tensor at target sample rate."""
        try:
            data, sample_rate = sf.read(str(audio_path), dtype="float32")
            if data.ndim == 1:
                waveform = torch.from_numpy(data).unsqueeze(0)
            else:
                waveform = torch.from_numpy(data.T)
        except Exception:
            waveform, sample_rate = torchaudio.load(str(audio_path))

        # Convert to mono if needed
        if self.config.mono and waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        # Resample if needed
        if sample_rate != self.config.sample_rate:
            resampler = self._get_resampler(sample_rate)
            waveform = resampler(waveform)

        return waveform, self.config.sample_rate

    def normalize_audio(self, waveform: torch.Tensor) -> torch.Tensor:
        """Normalize audio to target dBFS."""
        if not self.config.normalize:
            return waveform

        # Calculate current RMS
        rms = torch.sqrt(torch.mean(waveform**2))
        if rms == 0:
            return waveform

        # Calculate target RMS for target dBFS
        target_rms = 10 ** (self.config.target_dbfs / 20)
        gain = target_rms / rms

        # Apply gain with clipping prevention
        waveform = waveform * gain
        waveform = torch.clamp(waveform, -1.0, 1.0)

        return waveform

    def preprocess(self, audio_path: Path) -> tuple[torch.Tensor, AudioInfo]:
        """Full preprocessing pipeline: load, validate, resample, normalize."""
        errors = self.validate_audio(audio_path)
        if errors:
            raise ValueError(f"Audio validation failed: {'; '.join(errors)}")

        info = self.get_audio_info(audio_path)
        waveform, sr = self.load_audio(audio_path)
        waveform = self.normalize_audio(waveform)

        return waveform, info

    def preprocess_for_whisper(self, audio_path: Path) -> np.ndarray:
        """Preprocess audio for Whisper model input (returns numpy array)."""
        waveform, _ = self.preprocess(audio_path)
        # Whisper expects float32 numpy array, shape (n_samples,)
        return waveform.squeeze().numpy().astype(np.float32)

    def save_audio(self, waveform: torch.Tensor, output_path: Path, sample_rate: int | None = None) -> None:
        """Save waveform to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sr = sample_rate or self.config.sample_rate
        sf.write(str(output_path), waveform.squeeze().numpy(), sr)


def create_preprocessor_from_config(config_dict: dict[str, Any]) -> AudioPreprocessor:
    """Create AudioPreprocessor from configuration dictionary."""
    config = AudioConfig(
        sample_rate=config_dict.get("sample_rate", 16000),
        max_duration_seconds=config_dict.get("max_duration_seconds", 30.0),
        min_duration_seconds=config_dict.get("min_duration_seconds", 0.5),
        normalize=config_dict.get("normalize", True),
        target_dbfs=config_dict.get("target_dbfs", -20.0),
        mono=config_dict.get("mono", True),
    )
    return AudioPreprocessor(config)


def validate_uploaded_audio(
    file_path: Path,
    max_size_mb: float = 25.0,
    allowed_extensions: set[str] | None = None,
) -> list[str]:
    """Validate uploaded audio file for API endpoints."""
    errors = []
    allowed = allowed_extensions or {".wav", ".flac", ".mp3", ".ogg", ".m4a"}

    if not file_path.is_file():
        errors.append("File not found")
        return errors

    # Check file size
    size_mb = file_path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        errors.append(f"File too large: {size_mb:.1f}MB > {max_size_mb}MB")

    # Check extension
    if file_path.suffix.lower() not in allowed:
        errors.append(f"Unsupported format: {file_path.suffix}. Allowed: {', '.join(allowed)}")

    # Try to read audio info
    try:
        info = sf.info(str(file_path))
        if info.duration <= 0:
            errors.append("Audio has zero or negative duration")
        if info.channels <= 0:
            errors.append("Invalid channel count")
    except Exception as e:
        errors.append(f"Cannot read audio file: {e}")

    return errors


def chunk_long_audio(
    waveform: torch.Tensor,
    sample_rate: int,
    chunk_duration_seconds: float = 30.0,
    overlap_seconds: float = 1.0,
) -> list[torch.Tensor]:
    """Split long audio into overlapping chunks for processing."""
    chunk_samples = int(chunk_duration_seconds * sample_rate)
    overlap_samples = int(overlap_seconds * sample_rate)
    step_samples = chunk_samples - overlap_samples

    if waveform.shape[-1] <= chunk_samples:
        return [waveform]

    chunks = []
    for start in range(0, waveform.shape[-1], step_samples):
        end = min(start + chunk_samples, waveform.shape[-1])
        chunk = waveform[..., start:end]
        if chunk.shape[-1] > sample_rate * 0.5:  # At least 0.5s
            chunks.append(chunk)
        if end == waveform.shape[-1]:
            break

    return chunks