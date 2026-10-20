"""Speech dataset manifest format, validation, and splitting utilities."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any

logger = logging.getLogger(__name__)


SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg", ".m4a"}
SUPPORTED_LANGUAGES = {"en", "ta", "hi", "bn", "te", "mr", "gu", "kn", "ml", "pa", "or", "as"}


@dataclass(frozen=True)
class SpeechManifestEntry:
    sample_id: str
    audio_path: str
    transcript: str
    language: str
    split: str | None = None
    speaker_id: str | None = None
    source_dataset: str = "custom"
    license: str = "unknown"
    duration_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "audio_path": self.audio_path,
            "transcript": self.transcript,
            "language": self.language,
            "split": self.split,
            "speaker_id": self.speaker_id,
            "source_dataset": self.source_dataset,
            "license": self.license,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpeechManifestEntry:
        return cls(
            sample_id=data["sample_id"],
            audio_path=data["audio_path"],
            transcript=data["transcript"],
            language=data["language"],
            split=data.get("split"),
            speaker_id=data.get("speaker_id"),
            source_dataset=data.get("source_dataset", "custom"),
            license=data.get("license", "unknown"),
            duration_seconds=data.get("duration_seconds"),
        )


@dataclass
class ValidationResult:
    valid_entries: list[SpeechManifestEntry] = field(default_factory=list)
    rejected_entries: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_report(self) -> dict[str, Any]:
        return {
            "valid_count": len(self.valid_entries),
            "rejected_count": len(self.rejected_entries),
            "errors": self.errors,
            "warnings": self.warnings,
            "rejected_details": self.rejected_entries,
        }


def load_manifest(manifest_path: Path) -> list[SpeechManifestEntry]:
    """Load manifest from JSONL or CSV file."""
    entries: list[SpeechManifestEntry] = []
    if manifest_path.suffix == ".jsonl":
        with manifest_path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries.append(SpeechManifestEntry.from_dict(data))
                except json.JSONDecodeError as e:
                    logger.warning(f"Line {line_num}: Invalid JSON - {e}")
                except (KeyError, TypeError) as e:
                    logger.warning(f"Line {line_num}: Invalid entry format - {e}")
    elif manifest_path.suffix == ".csv":
        with manifest_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    entries.append(SpeechManifestEntry.from_dict(row))
                except (KeyError, TypeError) as e:
                    logger.warning(f"Row {reader.line_num}: Invalid entry format - {e}")
    else:
        raise ValueError(f"Unsupported manifest format: {manifest_path.suffix}. Use .jsonl or .csv")
    return entries


def validate_manifest(
    entries: list[SpeechManifestEntry],
    base_dir: Path | None = None,
    max_duration_seconds: float = 30.0,
    min_duration_seconds: float = 0.5,
) -> ValidationResult:
    """Validate manifest entries for audio existence, transcript quality, and metadata."""
    result = ValidationResult()
    seen_ids = set()
    seen_audio_paths = set()

    for entry in entries:
        rejection_reasons: list[str] = []

        # Check duplicate sample_id
        if entry.sample_id in seen_ids:
            rejection_reasons.append(f"Duplicate sample_id: {entry.sample_id}")
        seen_ids.add(entry.sample_id)

        # Check duplicate audio_path
        if entry.audio_path in seen_audio_paths:
            rejection_reasons.append(f"Duplicate audio_path: {entry.audio_path}")
        seen_audio_paths.add(entry.audio_path)

        # Validate audio path
        audio_path = Path(entry.audio_path)
        if base_dir:
            # Resolve relative paths against base_dir
            if not audio_path.is_absolute():
                audio_path = (base_dir / audio_path).resolve()
            else:
                audio_path = audio_path.resolve()
            try:
                audio_path.relative_to(base_dir.resolve())
            except ValueError:
                rejection_reasons.append(f"Audio path escapes base directory: {entry.audio_path}")

        if not audio_path.is_file():
            rejection_reasons.append(f"Audio file not found: {entry.audio_path}")
        elif audio_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
            rejection_reasons.append(f"Unsupported audio format: {audio_path.suffix}")

        # Validate transcript
        if not entry.transcript or not entry.transcript.strip():
            rejection_reasons.append("Empty transcript")
        elif len(entry.transcript) > 1000:
            rejection_reasons.append("Transcript exceeds maximum length (1000 chars)")

        # Validate language
        if entry.language not in SUPPORTED_LANGUAGES:
            rejection_reasons.append(f"Unsupported language: {entry.language}")

        # Validate split
        if entry.split and entry.split not in {"train", "validation", "test"}:
            rejection_reasons.append(f"Invalid split: {entry.split}")

        # Validate duration if provided
        if entry.duration_seconds is not None:
            if entry.duration_seconds < min_duration_seconds:
                rejection_reasons.append(f"Duration too short: {entry.duration_seconds}s < {min_duration_seconds}s")
            if entry.duration_seconds > max_duration_seconds:
                rejection_reasons.append(f"Duration too long: {entry.duration_seconds}s > {max_duration_seconds}s")

        if rejection_reasons:
            result.rejected_entries.append({
                "sample_id": entry.sample_id,
                "audio_path": entry.audio_path,
                "reasons": rejection_reasons,
            })
        else:
            result.valid_entries.append(entry)

    # Check for speaker leakage across splits
    if result.valid_entries:
        speaker_splits: dict[str, set[str]] = {}
        for entry in result.valid_entries:
            if entry.speaker_id:
                speaker_splits.setdefault(entry.speaker_id, set()).add(entry.split or "unspecified")
        for speaker_id, splits in speaker_splits.items():
            if len(splits) > 1:
                result.warnings.append(f"Speaker {speaker_id} appears in multiple splits: {splits}")

    return result


def create_splits(
    entries: list[SpeechManifestEntry],
    seed: int = 42,
    train_ratio: float = 0.7,
    validation_ratio: float = 0.15,
    test_ratio: float = 0.15,
    speaker_aware: bool = True,
) -> dict[str, list[SpeechManifestEntry]]:
    """Create deterministic train/validation/test splits, optionally speaker-aware."""
    if abs(train_ratio + validation_ratio + test_ratio - 1.0) > 1e-6:
        raise ValueError("Split ratios must sum to 1.0")

    entries_with_split = [e for e in entries if e.split]
    entries_without_split = [e for e in entries if not e.split]

    splits: dict[str, list[SpeechManifestEntry]] = {"train": [], "validation": [], "test": []}
    for entry in entries_with_split:
        if entry.split in splits:
            splits[entry.split].append(entry)

    if entries_without_split:
        rng = Random(seed)

        if speaker_aware:
            # Group by speaker_id, then split speakers
            speaker_groups: dict[str | None, list[SpeechManifestEntry]] = {}
            for entry in entries_without_split:
                speaker_groups.setdefault(entry.speaker_id, []).append(entry)

            speakers = list(speaker_groups.keys())
            rng.shuffle(speakers)

            n_speakers = len(speakers)
            train_end = max(1, round(n_speakers * train_ratio))
            val_end = min(n_speakers, train_end + max(1, round(n_speakers * validation_ratio)))

            train_speakers = set(speakers[:train_end])
            val_speakers = set(speakers[train_end:val_end])
            test_speakers = set(speakers[val_end:])

            for speaker_id, group_entries in speaker_groups.items():
                if speaker_id in train_speakers:
                    splits["train"].extend(group_entries)
                elif speaker_id in val_speakers:
                    splits["validation"].extend(group_entries)
                else:
                    splits["test"].extend(group_entries)
        else:
            rng.shuffle(entries_without_split)
            n = len(entries_without_split)
            train_end = max(1, round(n * train_ratio))
            val_end = min(n, train_end + max(1, round(n * validation_ratio)))

            splits["train"].extend(entries_without_split[:train_end])
            splits["validation"].extend(entries_without_split[train_end:val_end])
            splits["test"].extend(entries_without_split[val_end:])

    return splits


def generate_dataset_statistics(entries: list[SpeechManifestEntry]) -> dict[str, Any]:
    """Generate dataset statistics report."""
    if not entries:
        return {"total_samples": 0}

    languages: dict[str, int] = {}
    splits: dict[str, int] = {}
    speakers: set[str] = set()
    total_duration = 0.0
    durations: list[float] = []

    for entry in entries:
        languages[entry.language] = languages.get(entry.language, 0) + 1
        if entry.split:
            splits[entry.split] = splits.get(entry.split, 0) + 1
        if entry.speaker_id:
            speakers.add(entry.speaker_id)
        if entry.duration_seconds:
            total_duration += entry.duration_seconds
            durations.append(entry.duration_seconds)

    stats = {
        "total_samples": len(entries),
        "languages": languages,
        "splits": splits,
        "unique_speakers": len(speakers),
        "total_duration_seconds": round(total_duration, 2),
        "mean_duration_seconds": round(total_duration / len(durations), 2) if durations else 0,
        "min_duration_seconds": round(min(durations), 2) if durations else 0,
        "max_duration_seconds": round(max(durations), 2) if durations else 0,
    }
    return stats


def save_splits(
    splits: dict[str, list[SpeechManifestEntry]],
    output_dir: Path,
    manifest_name: str = "manifest",
) -> dict[str, Path]:
    """Save split manifests to JSONL files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = {}

    for split_name, entries in splits.items():
        output_path = output_dir / f"{manifest_name}_{split_name}.jsonl"
        with output_path.open("w", encoding="utf-8") as f:
            for entry in entries:
                entry_dict = entry.to_dict()
                entry_dict["split"] = split_name
                f.write(json.dumps(entry_dict, ensure_ascii=False) + "\n")
        saved_paths[split_name] = output_path

    return saved_paths


def save_validation_report(result: ValidationResult, output_path: Path) -> None:
    """Save validation report to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result.to_report(), indent=2, ensure_ascii=False), encoding="utf-8")


def save_dataset_config(
    output_dir: Path,
    source_manifest: Path,
    seed: int,
    train_ratio: float,
    validation_ratio: float,
    test_ratio: float,
    speaker_aware: bool,
    base_dir: Path | None = None,
) -> Path:
    """Save dataset preprocessing configuration."""
    config = {
        "source_manifest": str(source_manifest),
        "source_manifest_hash": hashlib.sha256(source_manifest.read_bytes()).hexdigest() if source_manifest.exists() else None,
        "base_dir": str(base_dir) if base_dir else None,
        "split_seed": seed,
        "train_ratio": train_ratio,
        "validation_ratio": validation_ratio,
        "test_ratio": test_ratio,
        "speaker_aware_split": speaker_aware,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "supported_languages": sorted(SUPPORTED_LANGUAGES),
        "supported_audio_extensions": sorted(SUPPORTED_AUDIO_EXTENSIONS),
    }
    config_path = output_dir / "dataset_config.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config_path