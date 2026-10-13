"""Reproducible synthetic dataset generator with provenance and leakage prevention.

Guarantees:
- Fully deterministic generation for a fixed seed and configuration.
- Stable checksum calculated strictly over deterministic row contents (excluding generation timestamp).
- Leakage-free subject identifiers that never encode profile targets.
- Explicit purity verification preventing synthetic and real rows from mixing silently.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any

from .games import (
    DEFAULT_LANGUAGE,
    SUPPORTED_GAMES,
    SUPPORTED_LANGUAGES,
    validate_game_language_pair,
)
from .quality import validate_synthetic_row
from .simulator import simulate_session
from .taxonomy import PROFILES, SCENARIO_DEFINITIONS, SUPPORTED_SCENARIOS

SIMULATOR_VERSION = "1.0"
SYNTHETIC_SCHEMA_VERSION = "1.0"
CONTENT_VERSION = "1.0"


@dataclass(frozen=True)
class SyntheticConfig:
    seed: int = 42
    subjects: int = 27
    sessions_per_subject: int = 2
    trials_per_session: int = 5
    dataset_version: str = "synthetic-1.0"
    languages: tuple[str, ...] = ("en",)
    games: tuple[str, ...] = SUPPORTED_GAMES
    scenarios: tuple[str, ...] = SUPPORTED_SCENARIOS
    modality_availability: float = 0.7
    difficulty_levels: tuple[int, ...] = (1, 2, 3, 4, 5)


def check_config(config: SyntheticConfig) -> None:
    if config.subjects < 3:
        raise ValueError("Synthetic generation requires at least 3 subjects")
    if config.sessions_per_subject < 1:
        raise ValueError("Synthetic generation requires at least 1 session per subject")
    if config.trials_per_session < 1:
        raise ValueError("Synthetic generation requires at least 1 trial per session")
    if not (0.0 <= config.modality_availability <= 1.0):
        raise ValueError("modality_availability must be between 0.0 and 1.0")

    unsupported_games = set(config.games) - set(SUPPORTED_GAMES)
    if unsupported_games:
        raise ValueError(f"Unsupported games: {sorted(unsupported_games)}")

    unsupported_scenarios = set(config.scenarios) - set(SUPPORTED_SCENARIOS)
    if unsupported_scenarios:
        raise ValueError(f"Unsupported scenarios: {sorted(unsupported_scenarios)}")

    unsupported_langs = set(config.languages) - SUPPORTED_LANGUAGES
    if unsupported_langs:
        raise ValueError(f"Unsupported languages: {sorted(unsupported_langs)}")

    if "ta" in config.languages:
        for g in config.games:
            if g != "mirror-match":
                raise ValueError(
                    f"Tamil ('ta') is only supported for language-neutral 'mirror-match', but '{g}' was requested."
                )


def _stable_checksum(rows: list[dict[str, Any]]) -> str:
    """Compute deterministic SHA256 checksum over rows alone, excluding timestamps and random salts."""
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def ensure_synthetic_purity(rows: list[dict[str, Any]]) -> None:
    """Guarantee that synthetic datasets and real research data cannot be silently mixed."""
    if not rows:
        return
    synthetic_flags = [bool(row.get("synthetic")) for row in rows]
    all_synthetic = all(synthetic_flags)
    none_synthetic = not any(synthetic_flags)
    if not (all_synthetic or none_synthetic):
        raise ValueError(
            "DATASET CONTAMINATION ERROR: Detected mixture of synthetic and non-synthetic rows. "
            "Synthetic data must remain completely isolated from real research or assessment data."
        )


def generate_dataset(config: SyntheticConfig = SyntheticConfig()) -> dict[str, Any]:
    """Generate a reproducible synthetic research dataset with complete provenance."""
    check_config(config)
    rng = Random(config.seed)

    rows: list[dict[str, Any]] = []
    eligible_count = 0
    ineligible_count = 0

    # Ensure profile targets are systematically distributed across subjects
    scenario_cycle = list(config.scenarios)

    for sub_idx in range(config.subjects):
        # Neutral subject ID to prevent label leakage via ID names
        subject_id = f"synthetic-sub-{sub_idx:04d}"
        assigned_scenario = scenario_cycle[sub_idx % len(scenario_cycle)]

        for sess_idx in range(config.sessions_per_subject):
            session_id = f"{subject_id}-sess-{sess_idx:03d}"
            game = config.games[(sub_idx * config.sessions_per_subject + sess_idx) % len(config.games)]
            lang = "ta" if ("ta" in config.languages and game == "mirror-match" and rng.random() < 0.5) else "en"
            diff = config.difficulty_levels[rng.randint(0, len(config.difficulty_levels) - 1)]
            if game in {"sound-quest-adventure", "letter-bubble-pop", "maze-runner-rush"}:
                diff = min(diff, 3)

            modality_on = rng.random() < config.modality_availability

            row = simulate_session(
                rng=rng,
                subject_id=subject_id,
                session_id=session_id,
                scenario=assigned_scenario,
                game=game,
                language=lang,
                trials_per_session=config.trials_per_session,
                difficulty=diff,
                modality_available=modality_on,
                schema_version=SYNTHETIC_SCHEMA_VERSION,
            )

            row["content_version"] = CONTENT_VERSION
            row["validation_issues"] = validate_synthetic_row(row)

            # Eligibility rule: must have no validation issues and must not be insufficient_observations
            is_eligible = (not row["validation_issues"]) and (assigned_scenario != "insufficient_observations")
            row["eligible"] = is_eligible
            if is_eligible:
                eligible_count += 1
            else:
                ineligible_count += 1

            rows.append(row)

    ensure_synthetic_purity(rows)

    checksum = _stable_checksum(rows)
    provenance = {
        "synthetic": True,
        "simulator_version": SIMULATOR_VERSION,
        "feature_schema_version": SYNTHETIC_SCHEMA_VERSION,
        "content_version": CONTENT_VERSION,
        "dataset_version": config.dataset_version,
        "seed": config.seed,
        "config": asdict(config),
        "scenario_definitions": SCENARIO_DEFINITIONS,
        "subjects": config.subjects,
        "sessions": len(rows),
        "eligible_sessions": eligible_count,
        "ineligible_sessions": ineligible_count,
        "scenario_counts": dict(Counter(row["target"] for row in rows)),
        "game_counts": dict(Counter(row["game_id"] for row in rows)),
        "language_counts": dict(Counter(row["language"] for row in rows)),
        "modality_counts": {
            "gaze_available": sum(bool(row["features"].get("gaze_available", {}).get("value")) for row in rows),
            "speech_available": sum(bool(row["features"].get("speech_available", {}).get("value")) for row in rows),
        },
        "data_checksum": checksum,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return {"metadata": provenance, "rows": rows}


def export_dataset(dataset: dict[str, Any], destination: Path) -> Path:
    """Export synthetic dataset to disk with file existence safety."""
    if destination.exists():
        raise FileExistsError(f"Dataset artifact destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(dataset, indent=2), encoding="utf-8")
    return destination

