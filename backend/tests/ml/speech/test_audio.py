"""Tests for audio preprocessing."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
import torch

from app.ml.speech.audio import (
    AudioConfig,
    AudioPreprocessor,
    AudioInfo,
    validate_uploaded_audio,
    chunk_long_audio,
)

# Formerly xfail on Windows (torchcodec DLL issues); verified passing on Windows with
# torch/torchaudio 2.11 on 2026-10-21, so failures are reported again.
requires_torchaudio_load = pytest.mark.torchaudio_load


class TestAudioConfig:
    def test_default_config(self):
        config = AudioConfig()
        assert config.sample_rate == 16000
        assert config.max_duration_seconds == 30.0
        assert config.normalize is True


class TestAudioPreprocessor:
    def setup_method(self):
        self.config = AudioConfig(sample_rate=16000, max_duration_seconds=10.0)
        self.preprocessor = AudioPreprocessor(self.config)

    def create_test_audio(self, path: Path, duration: float = 2.0, sample_rate: int = 16000, channels: int = 1):
        """Create a test audio file using soundfile."""
        num_samples = int(duration * sample_rate)
        waveform = torch.randn(channels, num_samples) * 0.1
        # Use soundfile to avoid torchaudio/torchcodec issues on Windows
        sf.write(str(path), waveform.squeeze().numpy(), sample_rate)

    def test_get_audio_info(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.wav"
            self.create_test_audio(audio_path, duration=2.0)

            info = self.preprocessor.get_audio_info(audio_path)
            assert info.sample_rate == 16000
            assert info.channels == 1
            assert info.duration_seconds == pytest.approx(2.0, abs=0.1)
            assert info.num_samples == 32000

    def test_validate_audio_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.wav"
            self.create_test_audio(audio_path, duration=2.0)

            errors = self.preprocessor.validate_audio(audio_path)
            assert len(errors) == 0

    def test_validate_audio_too_short(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.wav"
            self.create_test_audio(audio_path, duration=0.1)  # Below min_duration

            errors = self.preprocessor.validate_audio(audio_path)
            assert any("too short" in e for e in errors)

    def test_validate_audio_too_long(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.wav"
            self.create_test_audio(audio_path, duration=15.0)  # Above max_duration

            errors = self.preprocessor.validate_audio(audio_path)
            assert any("too long" in e for e in errors)

    @requires_torchaudio_load
    def test_load_audio_resamples(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.wav"
            self.create_test_audio(audio_path, duration=1.0, sample_rate=44100)  # Different sample rate

            waveform, sr = self.preprocessor.load_audio(audio_path)
            assert sr == 16000
            assert waveform.shape[0] == 1  # Mono

    def test_normalize_audio(self):
        waveform = torch.tensor([[0.01, 0.02, -0.01, -0.02]])  # Low amplitude
        normalized = self.preprocessor.normalize_audio(waveform)

        # Should be scaled up
        assert normalized.abs().max() > waveform.abs().max()
        assert normalized.abs().max() <= 1.0  # Clamped

    @requires_torchaudio_load
    def test_preprocess_for_whisper(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.wav"
            self.create_test_audio(audio_path, duration=1.0)

            array = self.preprocessor.preprocess_for_whisper(audio_path)
            assert isinstance(array, np.ndarray)
            assert array.dtype == np.float32
            assert array.ndim == 1
            assert len(array) == 16000  # 1 second at 16kHz


class TestValidateUploadedAudio:
    def test_valid_wav(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.wav"
            # Create minimal valid WAV using soundfile
            waveform = torch.randn(1, 16000) * 0.1
            sf.write(str(audio_path), waveform.squeeze().numpy(), 16000)

            errors = validate_uploaded_audio(audio_path)
            assert len(errors) == 0

    def test_file_too_large(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "large.wav"
            # Create a file > 25MB
            audio_path.write_bytes(b"x" * (26 * 1024 * 1024))

            errors = validate_uploaded_audio(audio_path)
            assert any("too large" in e for e in errors)

    def test_invalid_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "test.xyz"
            audio_path.write_bytes(b"fake")

            errors = validate_uploaded_audio(audio_path)
            assert any("Unsupported format" in e for e in errors)

    def test_corrupted_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "corrupt.wav"
            audio_path.write_bytes(b"not a wav file")

            errors = validate_uploaded_audio(audio_path)
            assert any("Cannot read audio file" in e for e in errors)


class TestChunkLongAudio:
    def test_short_audio_not_chunked(self):
        waveform = torch.randn(1, 16000)  # 1 second
        chunks = chunk_long_audio(waveform, 16000, chunk_duration_seconds=30.0)
        assert len(chunks) == 1
        assert chunks[0].shape == waveform.shape

    def test_long_audio_chunked(self):
        waveform = torch.randn(1, 16000 * 60)  # 60 seconds
        chunks = chunk_long_audio(waveform, 16000, chunk_duration_seconds=30.0, overlap_seconds=1.0)
        # 60s with 30s chunks and 1s overlap: chunks at 0-30, 29-59, 58-60 (3 chunks, last is short)
        assert len(chunks) >= 2
        assert chunks[0].shape[-1] == 16000 * 30
        # Last chunk may be shorter
        assert chunks[-1].shape[-1] <= 16000 * 30


class TestCreatePreprocessorFromConfig:
    def test_from_dict(self):
        from app.ml.speech.audio import create_preprocessor_from_config

        config_dict = {
            "sample_rate": 22050,
            "max_duration_seconds": 60.0,
            "normalize": False,
        }
        preprocessor = create_preprocessor_from_config(config_dict)
        assert preprocessor.config.sample_rate == 22050
        assert preprocessor.config.max_duration_seconds == 60.0
        assert preprocessor.config.normalize is False