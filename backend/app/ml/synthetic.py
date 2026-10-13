"""Synthetic interaction-profile research pipeline.

This module generates simulator-defined behavior profiles only. Its labels are
not clinical labels and its artifacts must never enter the production registry.
"""

from __future__ import annotations

import hashlib
import json
import pickle
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Any

from .datasets import subject_level_split
from .feature_registry import REGISTRY_BY_NAME
from .models import BaselineModel, GradientBoostingBaseline, LogisticBaseline, RandomForestBaseline

SIMULATOR_VERSION = "1.0"
SYNTHETIC_SCHEMA_VERSION = "1.0"
SUPPORTED_GAMES = (
    "letter-detective",
    "mirror-match",
    "word-flash",
    "sequence-quest",
    "word-maze",
    "sound-quest-adventure",
    "letter-bubble-pop",
    "maze-runner-rush",
)
SUPPORTED_LANGUAGES = {"en"}
LANGUAGE_NEUTRAL_GAMES = {"mirror-match"}
SCENARIO_DEFINITIONS: dict[str, dict[str, str]] = {
    "consistent_responses": {"definition": "Stable timing and high completion with few errors."},
    "variable_response_timing": {"definition": "Timing varies substantially while responses remain mostly complete."},
    "high_error_frequency": {"definition": "Frequent incorrect responses across simulated tasks."},
    "repeated_symbol_confusions": {"definition": "Elevated errors on symbol and word-recognition tasks."},
    "reduced_reading_response_coverage": {"definition": "Speech tasks have incomplete or unavailable response observations."},
    "attention_variability": {"definition": "Elevated pauses, hints, and timing variability in visual tasks."},
    "working_memory_task_difficulty": {"definition": "Lower performance concentrated in sequence tasks."},
    "mixed_interaction_profile": {"definition": "Moderate variation across accuracy, timing, and completion."},
    "insufficient_observations": {"definition": "Too little completed evidence for an eligible research row."},
}


@dataclass(frozen=True)
class SyntheticConfig:
    seed: int = 42
    subjects: int = 24
    sessions_per_subject: int = 2
    trials_per_session: int = 5
    dataset_version: str = "synthetic-1.0"
    languages: tuple[str, ...] = ("en",)
    games: tuple[str, ...] = SUPPORTED_GAMES
    scenarios: tuple[str, ...] = tuple(SCENARIO_DEFINITIONS)
    modality_availability: float = .7


def _check_config(config: SyntheticConfig) -> None:
    if config.subjects < 3 or config.sessions_per_subject < 1 or config.trials_per_session < 1:
        raise ValueError("synthetic configuration requires at least three subjects and one trial")
    if not 0 <= config.modality_availability <= 1:
        raise ValueError("modality_availability must be between zero and one")
    if not set(config.games) <= set(SUPPORTED_GAMES):
        raise ValueError("unsupported game in synthetic configuration")
    if not set(config.scenarios) <= set(SCENARIO_DEFINITIONS):
        raise ValueError("unsupported synthetic scenario")
    if not set(config.languages) <= SUPPORTED_LANGUAGES:
        raise ValueError("unsupported synthetic language")
    if "ta" in config.languages and any(game not in LANGUAGE_NEUTRAL_GAMES for game in config.games):
        raise ValueError("Tamil simulation is only available for language-neutral mirror-match content")


def _clip(name: str, value: float | int | None) -> float | int | None:
    if value is None:
        return None
    definition = REGISTRY_BY_NAME[name]
    if definition.minimum is not None:
        value = max(definition.minimum, value)
    if definition.maximum is not None:
        value = min(definition.maximum, value)
    return value


def _feature(name: str, value: float | int | None, available: bool = True) -> dict[str, Any]:
    definition = REGISTRY_BY_NAME[name]
    return {
        "name": name,
        "value": _clip(name, value) if available else None,
        "unit": definition.unit,
        "source": "synthetic_simulator",
        "domain": definition.domain,
        "available": available,
        "status": "available" if available else "missing",
        "modality": definition.modality,
        "extraction_version": SYNTHETIC_SCHEMA_VERSION,
        "calculation_version": SYNTHETIC_SCHEMA_VERSION,
    }


def _features(rng: Random, scenario: str, game: str, trials: int, modality_available: bool) -> dict[str, dict[str, Any]]:
    accuracy = {"consistent_responses": .92, "variable_response_timing": .82, "high_error_frequency": .45, "repeated_symbol_confusions": .58, "reduced_reading_response_coverage": .78, "attention_variability": .68, "working_memory_task_difficulty": .72, "mixed_interaction_profile": .70, "insufficient_observations": .5}[scenario]
    reaction = {"consistent_responses": 750, "variable_response_timing": 1100, "high_error_frequency": 1250, "repeated_symbol_confusions": 1050, "reduced_reading_response_coverage": 900, "attention_variability": 1150, "working_memory_task_difficulty": 1000, "mixed_interaction_profile": 980, "insufficient_observations": 900}[scenario]
    variance = 180 if scenario in {"consistent_responses", "high_error_frequency"} else 1100
    if scenario == "attention_variability":
        variance = 1800
    correct = _clip("overall_accuracy", accuracy + rng.gauss(0, .04))
    result = {
        "overall_accuracy": _feature("overall_accuracy", correct),
        "incorrect_response_rate": _feature("incorrect_response_rate", 1 - float(correct)),
        "mean_reaction_time_ms": _feature("mean_reaction_time_ms", rng.gauss(reaction, 70)),
        "median_reaction_time_ms": _feature("median_reaction_time_ms", rng.gauss(reaction, 55)),
        "reaction_time_variance_ms2": _feature("reaction_time_variance_ms2", max(0, rng.gauss(variance, variance * .15))),
        "mean_hesitation_time_ms": _feature("mean_hesitation_time_ms", max(0, rng.gauss(160 if scenario != "consistent_responses" else 70, 35))),
        "total_error_count": _feature("total_error_count", round((1 - float(correct)) * trials)),
        "completion_rate": _feature("completion_rate", .65 if scenario == "insufficient_observations" else max(.5, rng.gauss(.96, .03))),
        "pause_count": _feature("pause_count", rng.randint(0, 1 if scenario == "consistent_responses" else 5)),
        "hint_count": _feature("hint_count", rng.randint(0, 1 if scenario == "consistent_responses" else 4)),
    }
    if game == "sequence-quest" and scenario == "working_memory_task_difficulty":
        result["overall_accuracy"] = _feature("overall_accuracy", rng.gauss(.45, .05))
        result["incorrect_response_rate"] = _feature("incorrect_response_rate", 1 - float(result["overall_accuracy"]["value"]))
    for name in ("gaze_available", "gaze_sample_count", "gaze_fixation_count", "gaze_mean_fixation_duration_ms", "gaze_max_fixation_duration_ms", "gaze_target_fixation_time_ms", "gaze_distractor_fixation_time_ms", "gaze_time_to_first_target_fixation_ms", "gaze_fixation_switch_count", "gaze_regression_count", "gaze_saccade_variance_ms2", "gaze_scanpath_entropy", "gaze_horizontal_saccade_bias", "gaze_coverage_ratio"):
        if not modality_available:
            result[name] = _feature(name, None, False)
        elif name == "gaze_available":
            result[name] = _feature(name, 1)
        elif name == "gaze_horizontal_saccade_bias":
            result[name] = _feature(name, rng.uniform(-.35, .35))
        elif name == "gaze_coverage_ratio":
            result[name] = _feature(name, rng.uniform(.35, .95))
        else:
            result[name] = _feature(name, rng.randint(3, 80) if "count" in name else rng.uniform(100, 1200))
    speech_names = ("speech_available", "speech_reading_duration_ms", "speech_words_per_minute", "speech_substitution_count", "speech_omission_count", "speech_insertion_count", "speech_repetition_count", "speech_error_rate", "speech_pause_count", "speech_mean_pause_duration_ms", "speech_median_pause_duration_ms", "speech_pause_variability_ms2", "text_token_count", "text_unique_token_count", "text_type_token_ratio", "text_repetition_count")
    speech_available = modality_available and game in {"sound-quest-adventure", "letter-bubble-pop", "maze-runner-rush"} and scenario != "reduced_reading_response_coverage"
    for name in speech_names:
        if not speech_available:
            result[name] = _feature(name, None, False)
        elif name == "speech_available":
            result[name] = _feature(name, 1)
        elif name in {"speech_error_rate", "text_type_token_ratio"}:
            result[name] = _feature(name, rng.uniform(0, .35))
        elif "count" in name or name.endswith("_count"):
            result[name] = _feature(name, rng.randint(0, 3))
        else:
            result[name] = _feature(name, rng.uniform(1, 20) if "token" in name else rng.uniform(500, 5000))
    return result


def _stable_checksum(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def validate_synthetic_row(row: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for name, item in row.get("features", {}).items():
        definition = REGISTRY_BY_NAME.get(name)
        if definition is None:
            issues.append(f"unknown_feature:{name}")
            continue
        value = item.get("value")
        if value is not None and not isinstance(value, (int, float)):
            issues.append(f"invalid_type:{name}")
        if value is not None and definition.minimum is not None and value < definition.minimum:
            issues.append(f"below_minimum:{name}")
        if value is not None and definition.maximum is not None and value > definition.maximum:
            issues.append(f"above_maximum:{name}")
        if bool(item.get("available")) != (value is not None):
            issues.append(f"availability_mismatch:{name}")
    if not row.get("synthetic") or not row.get("simulator_version"):
        issues.append("missing_synthetic_provenance")
    return issues


def generate_dataset(config: SyntheticConfig = SyntheticConfig()) -> dict[str, Any]:
    _check_config(config)
    rng = Random(config.seed)
    rows: list[dict[str, Any]] = []
    for subject_index in range(config.subjects):
        subject_id = f"synthetic-subject-{subject_index:04d}"
        scenario = config.scenarios[subject_index % len(config.scenarios)]
        for session_index in range(config.sessions_per_subject):
            game = config.games[(subject_index * config.sessions_per_subject + session_index) % len(config.games)]
            language = "ta" if "ta" in config.languages and game == "mirror-match" and rng.random() < .5 else "en"
            completed_trials = 1 if scenario == "insufficient_observations" else config.trials_per_session
            row = {
                "subject_id": subject_id,
                "session_id": f"{subject_id}-session-{session_index:03d}",
                "target": scenario,
                "synthetic": True,
                "simulator_version": SIMULATOR_VERSION,
                "feature_schema_version": SYNTHETIC_SCHEMA_VERSION,
                "game_id": game,
                "language": language,
                "content_version": "1.0",
                "scenario": scenario,
                "features": _features(rng, scenario, game, completed_trials, rng.random() < config.modality_availability),
            }
            row["validation_issues"] = validate_synthetic_row(row)
            row["eligible"] = not row["validation_issues"] and scenario != "insufficient_observations"
            rows.append(row)
    eligible = [row for row in rows if row["eligible"]]
    provenance = {
        "synthetic": True,
        "simulator_version": SIMULATOR_VERSION,
        "feature_schema_version": SYNTHETIC_SCHEMA_VERSION,
        "dataset_version": config.dataset_version,
        "seed": config.seed,
        "config": asdict(config),
        "scenario_definitions": SCENARIO_DEFINITIONS,
        "subjects": config.subjects,
        "sessions": len(rows),
        "eligible_sessions": len(eligible),
        "scenario_counts": dict(Counter(row["target"] for row in rows)),
        "game_counts": dict(Counter(row["game_id"] for row in rows)),
        "language_counts": dict(Counter(row["language"] for row in rows)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_checksum": _stable_checksum(rows),
    }
    return {"metadata": provenance, "rows": rows}


def export_dataset(dataset: dict[str, Any], destination: Path) -> Path:
    if destination.exists():
        raise FileExistsError(f"dataset artifact already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(dataset, indent=2), encoding="utf-8")
    return destination


def _estimator(name: str, feature_names: list[str]) -> Any:
    if name == "logistic_regression":
        return LogisticBaseline(feature_names)
    if name == "random_forest":
        return RandomForestBaseline(feature_names)
    if name == "gradient_boosting":
        return GradientBoostingBaseline(feature_names)
    if name == "dummy":
        from sklearn.dummy import DummyClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import Pipeline
        return Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", DummyClassifier(strategy="prior"))])
    raise ValueError(f"unsupported synthetic estimator: {name}")


def train_synthetic_models(dataset: dict[str, Any], output_dir: Path, algorithms: tuple[str, ...] = ("dummy", "logistic_regression", "random_forest")) -> dict[str, Any]:
    rows = [row for row in dataset["rows"] if row.get("eligible")]
    if not rows:
        raise ValueError("synthetic dataset has no eligible rows")
    feature_names = sorted(REGISTRY_BY_NAME)
    split = subject_level_split(rows, seed=int(dataset["metadata"]["seed"]))
    labels = [row["target"] for row in rows]
    train_subjects = {row["subject_id"] for row in split["train"]}
    results: dict[str, Any] = {}
    output_dir.mkdir(parents=True, exist_ok=True)
    for algorithm in algorithms:
        model = _estimator(algorithm, feature_names)
        train_rows = split["train"]
        train_labels = [row["target"] for row in train_rows]
        matrix = [[row["features"].get(name, {}).get("value") for name in feature_names] for row in train_rows]
        model.fit(matrix, train_labels) if algorithm == "dummy" else model.fit(train_rows, train_labels)
        metrics: dict[str, Any] = {}
        for partition in ("validation", "test"):
            partition_rows = split[partition]
            if not partition_rows:
                continue
            actual = [row["target"] for row in partition_rows]
            matrix = [[row["features"].get(name, {}).get("value") for name in feature_names] for row in partition_rows]
            predicted = model.predict(matrix).tolist() if algorithm == "dummy" else model.predict(partition_rows)
            metrics[partition] = {"accuracy": sum(a == p for a, p in zip(actual, predicted)) / len(actual), "classes": sorted(set(actual))}
        artifact = output_dir / f"{algorithm}.pkl"
        with artifact.open("wb") as handle:
            pickle.dump(model, handle)
        results[algorithm] = {"synthetic": True, "intended_use": "simulator_profile_classification", "clinical_use": "prohibited", "feature_schema_version": SYNTHETIC_SCHEMA_VERSION, "dataset_checksum": dataset["metadata"]["data_checksum"], "feature_names": feature_names, "algorithm": algorithm, "metrics": metrics, "artifact": artifact.name, "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(), "train_subjects": len(train_subjects), "validation_subjects": len({row["subject_id"] for row in split["validation"]}), "test_subjects": len({row["subject_id"] for row in split["test"]})}
        (output_dir / f"{algorithm}.json").write_text(json.dumps(results[algorithm], indent=2), encoding="utf-8")
    return results
