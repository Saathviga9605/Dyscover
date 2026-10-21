"""Tests for speech dataset manifest and validation."""

from __future__ import annotations

import pytest

# Optional offline stack (requirements-speech-ml.txt); skipped, not failed, without it.
for _name in ("torch", "soundfile", "transformers", "jiwer"):
    pytest.importorskip(_name, reason="optional speech-ML stack not installed: pip install -r requirements-speech-ml.txt")

import json
import tempfile
from pathlib import Path

import pytest

from app.ml.speech.dataset import (
    SpeechManifestEntry,
    ValidationResult,
    load_manifest,
    validate_manifest,
    create_splits,
    generate_dataset_statistics,
    save_splits,
    save_validation_report,
    save_dataset_config,
)


class TestSpeechManifestEntry:
    def test_entry_creation(self):
        entry = SpeechManifestEntry(
            sample_id="test-001",
            audio_path="audio/test.wav",
            transcript="hello world",
            language="en",
            split="train",
            speaker_id="spk-001",
        )
        assert entry.sample_id == "test-001"
        assert entry.transcript == "hello world"
        assert entry.language == "en"

    def test_entry_serialization(self):
        entry = SpeechManifestEntry(
            sample_id="test-001",
            audio_path="audio/test.wav",
            transcript="hello world",
            language="en",
        )
        data = entry.to_dict()
        assert data["sample_id"] == "test-001"
        assert data["transcript"] == "hello world"

        restored = SpeechManifestEntry.from_dict(data)
        assert restored.sample_id == entry.sample_id
        assert restored.transcript == entry.transcript


class TestLoadManifest:
    def test_load_jsonl(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"sample_id": "1", "audio_path": "a.wav", "transcript": "hello", "language": "en"}\n')
            f.write('{"sample_id": "2", "audio_path": "b.wav", "transcript": "world", "language": "en"}\n')
            path = Path(f.name)

        try:
            entries = load_manifest(path)
            assert len(entries) == 2
            assert entries[0].sample_id == "1"
            assert entries[1].transcript == "world"
        finally:
            path.unlink()

    def test_load_csv(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("sample_id,audio_path,transcript,language\n")
            f.write("1,a.wav,hello,en\n")
            f.write("2,b.wav,world,en\n")
            path = Path(f.name)

        try:
            entries = load_manifest(path)
            assert len(entries) == 2
            assert entries[0].sample_id == "1"
        finally:
            path.unlink()

    def test_invalid_format(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("invalid")
            path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Unsupported manifest format"):
                load_manifest(path)
        finally:
            path.unlink()


class TestValidateManifest:
    def _create_dummy_audio(self, tmpdir: str, name: str) -> Path:
        audio_path = Path(tmpdir) / "audio" / name
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
        return audio_path

    def test_valid_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = self._create_dummy_audio(tmpdir, "test.wav")
            entry = SpeechManifestEntry(
                sample_id="1",
                audio_path=str(audio_path),
                transcript="hello world",
                language="en",
            )
            result = validate_manifest([entry], base_dir=Path(tmpdir))
            assert len(result.valid_entries) == 1
            assert len(result.rejected_entries) == 0

    def test_missing_audio(self):
        entry = SpeechManifestEntry(
            sample_id="1",
            audio_path="nonexistent.wav",
            transcript="hello world",
            language="en",
        )
        result = validate_manifest([entry])
        assert len(result.valid_entries) == 0
        assert len(result.rejected_entries) == 1
        assert "not found" in result.rejected_entries[0]["reasons"][0]

    def test_empty_transcript(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = self._create_dummy_audio(tmpdir, "test.wav")
            entry = SpeechManifestEntry(
                sample_id="1",
                audio_path=str(audio_path),
                transcript="",
                language="en",
            )
            result = validate_manifest([entry], base_dir=Path(tmpdir))
            assert len(result.valid_entries) == 0
            assert len(result.rejected_entries) == 1
            assert "Empty transcript" in result.rejected_entries[0]["reasons"][0]

    def test_unsupported_language(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = self._create_dummy_audio(tmpdir, "test.wav")
            entry = SpeechManifestEntry(
                sample_id="1",
                audio_path=str(audio_path),
                transcript="hello",
                language="fr",  # Not in supported languages
            )
            result = validate_manifest([entry], base_dir=Path(tmpdir))
            assert len(result.valid_entries) == 0
            assert "Unsupported language" in result.rejected_entries[0]["reasons"][0]

    def test_duplicate_sample_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = self._create_dummy_audio(tmpdir, "test.wav")
            entries = [
                SpeechManifestEntry(sample_id="1", audio_path=str(audio_path), transcript="hello", language="en"),
                SpeechManifestEntry(sample_id="1", audio_path=str(audio_path), transcript="world", language="en"),
            ]
            result = validate_manifest(entries, base_dir=Path(tmpdir))
            # First entry valid, second rejected for duplicate ID
            assert len(result.valid_entries) == 1
            assert len(result.rejected_entries) == 1
            assert "Duplicate sample_id" in result.rejected_entries[0]["reasons"][0]

    def test_speaker_leakage_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path1 = self._create_dummy_audio(tmpdir, "test1.wav")
            audio_path2 = self._create_dummy_audio(tmpdir, "test2.wav")
            entries = [
                SpeechManifestEntry(sample_id="1", audio_path=str(audio_path1), transcript="hello", language="en", speaker_id="spk1", split="train"),
                SpeechManifestEntry(sample_id="2", audio_path=str(audio_path2), transcript="world", language="en", speaker_id="spk1", split="test"),
            ]
            result = validate_manifest(entries, base_dir=Path(tmpdir))
            assert len(result.warnings) == 1
            assert "Speaker spk1 appears in multiple splits" in result.warnings[0]


class TestCreateSplits:
    def test_manual_splits_preserved(self):
        entries = [
            SpeechManifestEntry(sample_id="1", audio_path="a.wav", transcript="hello", language="en", split="train"),
            SpeechManifestEntry(sample_id="2", audio_path="b.wav", transcript="world", language="en", split="test"),
        ]
        splits = create_splits(entries, speaker_aware=False)
        assert len(splits["train"]) == 1
        assert len(splits["test"]) == 1
        assert len(splits["validation"]) == 0

    def test_deterministic_splits(self):
        entries = [
            SpeechManifestEntry(sample_id=str(i), audio_path=f"{i}.wav", transcript=f"text {i}", language="en")
            for i in range(100)
        ]
        splits1 = create_splits(entries, seed=42, speaker_aware=False)
        splits2 = create_splits(entries, seed=42, speaker_aware=False)
        assert len(splits1["train"]) == len(splits2["train"])
        assert splits1["train"][0].sample_id == splits2["train"][0].sample_id

    def test_speaker_aware_splits(self):
        entries = []
        for spk in range(10):
            for i in range(5):
                entries.append(SpeechManifestEntry(
                    sample_id=f"spk{spk}-{i}",
                    audio_path=f"spk{spk}-{i}.wav",
                    transcript="text",
                    language="en",
                    speaker_id=f"spk{spk}",
                ))
        splits = create_splits(entries, seed=42, speaker_aware=True)
        # Check that speakers are not split
        train_speakers = {e.speaker_id for e in splits["train"]}
        val_speakers = {e.speaker_id for e in splits["validation"]}
        test_speakers = {e.speaker_id for e in splits["test"]}
        assert train_speakers.isdisjoint(val_speakers)
        assert train_speakers.isdisjoint(test_speakers)
        assert val_speakers.isdisjoint(test_speakers)


class TestGenerateDatasetStatistics:
    def test_statistics(self):
        entries = [
            SpeechManifestEntry(sample_id="1", audio_path="a.wav", transcript="hello world", language="en", duration_seconds=2.0),
            SpeechManifestEntry(sample_id="2", audio_path="b.wav", transcript="test", language="en", duration_seconds=3.0),
            SpeechManifestEntry(sample_id="3", audio_path="c.wav", transcript="foo", language="ta", duration_seconds=1.5),
        ]
        stats = generate_dataset_statistics(entries)
        assert stats["total_samples"] == 3
        assert stats["languages"]["en"] == 2
        assert stats["languages"]["ta"] == 1
        assert stats["total_duration_seconds"] == 6.5
        assert stats["mean_duration_seconds"] == pytest.approx(2.17, rel=0.01)


class TestSaveSplits:
    def test_save_splits(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            entries = [
                SpeechManifestEntry(sample_id="1", audio_path="a.wav", transcript="hello", language="en"),
                SpeechManifestEntry(sample_id="2", audio_path="b.wav", transcript="world", language="en"),
            ]
            splits = {"train": entries[:1], "validation": entries[1:], "test": []}
            saved = save_splits(splits, output_dir, "test")

            assert saved["train"].exists()
            assert saved["validation"].exists()

            # Verify content
            with saved["train"].open() as f:
                lines = f.readlines()
                assert len(lines) == 1
                data = json.loads(lines[0])
                assert data["sample_id"] == "1"
                assert data["split"] == "train"


class TestSaveValidationReport:
    def test_save_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ValidationResult(
                valid_entries=[],
                rejected_entries=[{"sample_id": "1", "reasons": ["missing audio"]}],
            )
            report_path = Path(tmpdir) / "report.json"
            save_validation_report(result, report_path)

            assert report_path.exists()
            with report_path.open() as f:
                data = json.load(f)
                assert data["rejected_count"] == 1


class TestSaveDatasetConfig:
    def test_save_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = save_dataset_config(
                Path(tmpdir),
                Path("manifest.jsonl"),
                seed=42,
                train_ratio=0.7,
                validation_ratio=0.15,
                test_ratio=0.15,
                speaker_aware=True,
            )
            assert config_path.exists()
            with config_path.open() as f:
                data = json.load(f)
                assert data["split_seed"] == 42
                assert data["speaker_aware_split"] is True