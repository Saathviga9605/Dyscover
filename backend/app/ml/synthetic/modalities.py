"""Simulation of gaze and speech modalities according to canonical feature registry schemas.

Privacy Notice:
Synthetic observations generate structured statistical features only.
No raw audio files, camera frames, or purported real child transcripts are simulated or persisted.
"""

from __future__ import annotations

from random import Random
from typing import Any

from app.ml.feature_registry import REGISTRY_BY_NAME

GAZE_FEATURE_NAMES = (
    "gaze_available",
    "gaze_sample_count",
    "gaze_fixation_count",
    "gaze_mean_fixation_duration_ms",
    "gaze_max_fixation_duration_ms",
    "gaze_target_fixation_time_ms",
    "gaze_distractor_fixation_time_ms",
    "gaze_time_to_first_target_fixation_ms",
    "gaze_fixation_switch_count",
    "gaze_regression_count",
    "gaze_saccade_variance_ms2",
    "gaze_scanpath_entropy",
    "gaze_horizontal_saccade_bias",
    "gaze_coverage_ratio",
)

SPEECH_FEATURE_NAMES = (
    "speech_available",
    "speech_reading_duration_ms",
    "speech_words_per_minute",
    "speech_substitution_count",
    "speech_omission_count",
    "speech_insertion_count",
    "speech_repetition_count",
    "speech_error_rate",
    "speech_pause_count",
    "speech_mean_pause_duration_ms",
    "speech_median_pause_duration_ms",
    "speech_pause_variability_ms2",
    "text_token_count",
    "text_unique_token_count",
    "text_type_token_ratio",
    "text_repetition_count",
)


def _clip_val(name: str, val: float | int | None) -> float | int | None:
    if val is None:
        return None
    definition = REGISTRY_BY_NAME.get(name)
    if definition is None:
        return val
    if definition.minimum is not None:
        val = max(definition.minimum, val)
    if definition.maximum is not None:
        val = min(definition.maximum, val)
    if definition.datatype == "integer":
        val = int(round(val))
    return val


def make_feature_record(
    name: str,
    value: float | int | None,
    available: bool = True,
    schema_version: str = "1.0",
) -> dict[str, Any]:
    definition = REGISTRY_BY_NAME[name]
    clipped = _clip_val(name, value) if available else None
    return {
        "name": name,
        "value": clipped,
        "unit": definition.unit,
        "source": "synthetic_simulator",
        "domain": definition.domain,
        "available": available and (clipped is not None),
        "status": "available" if (available and clipped is not None) else "missing",
        "modality": definition.modality,
        "extraction_version": schema_version,
        "calculation_version": schema_version,
    }


def simulate_gaze_features(
    rng: Random,
    available: bool,
    scenario: str,
    schema_version: str = "1.0",
    calibration_quality: float = 1.0,
) -> dict[str, dict[str, Any]]:
    """Simulate session-level gaze features adhering strictly to canonical definitions."""
    records: dict[str, dict[str, Any]] = {}
    if not available:
        for name in GAZE_FEATURE_NAMES:
            records[name] = make_feature_record(name, None, available=False, schema_version=schema_version)
        return records

    # High attention variability vs standard scanpaths
    is_distracted = scenario == "attention_variability"
    sample_count = int(rng.gauss(400 * calibration_quality, 40))
    fixation_count = int(rng.gauss(35 * calibration_quality, 6))

    mean_fix_dur = rng.gauss(260.0, 30.0)
    max_fix_dur = mean_fix_dur + rng.uniform(200.0, 600.0)

    target_time = rng.gauss(2200.0, 250.0) if not is_distracted else rng.gauss(1200.0, 200.0)
    distractor_time = rng.gauss(400.0, 80.0) if not is_distracted else rng.gauss(1400.0, 220.0)
    latency_to_target = rng.gauss(320.0, 45.0) if not is_distracted else rng.gauss(680.0, 90.0)

    switch_count = rng.randint(4, 16) if not is_distracted else rng.randint(18, 32)
    regression_count = rng.randint(1, 5) if scenario != "repeated_symbol_confusions" else rng.randint(6, 14)
    saccade_var = rng.gauss(6000.0, 800.0) if not is_distracted else rng.gauss(18000.0, 2500.0)
    scanpath_entropy = rng.uniform(1.2, 2.2) if not is_distracted else rng.uniform(2.6, 3.4)
    horizontal_bias = rng.uniform(-0.15, 0.25)
    coverage_ratio = (
        rng.uniform(0.65, 0.95) * calibration_quality
        if not is_distracted
        else rng.uniform(0.35, 0.60) * calibration_quality
    )

    values: dict[str, float | int] = {
        "gaze_available": 1,
        "gaze_sample_count": sample_count,
        "gaze_fixation_count": fixation_count,
        "gaze_mean_fixation_duration_ms": mean_fix_dur,
        "gaze_max_fixation_duration_ms": max_fix_dur,
        "gaze_target_fixation_time_ms": target_time,
        "gaze_distractor_fixation_time_ms": distractor_time,
        "gaze_time_to_first_target_fixation_ms": latency_to_target,
        "gaze_fixation_switch_count": switch_count,
        "gaze_regression_count": regression_count,
        "gaze_saccade_variance_ms2": saccade_var,
        "gaze_scanpath_entropy": scanpath_entropy,
        "gaze_horizontal_saccade_bias": horizontal_bias,
        "gaze_coverage_ratio": coverage_ratio,
    }

    for name in GAZE_FEATURE_NAMES:
        records[name] = make_feature_record(name, values[name], available=True, schema_version=schema_version)
    return records


def simulate_speech_features(
    rng: Random,
    available: bool,
    scenario: str,
    game: str,
    schema_version: str = "1.0",
) -> dict[str, dict[str, Any]]:
    """Simulate session-level speech features for speech-enabled games."""
    records: dict[str, dict[str, Any]] = {}
    is_speech_game = game in {"sound-quest-adventure", "letter-bubble-pop", "maze-runner-rush"}
    speech_eligible = available and is_speech_game and (scenario != "reduced_reading_response_coverage")

    if not speech_eligible:
        for name in SPEECH_FEATURE_NAMES:
            records[name] = make_feature_record(name, None, available=False, schema_version=schema_version)
        return records

    # High error frequency scenario has elevated reading errors
    high_errors = scenario == "high_error_frequency"
    duration_ms = rng.gauss(4200.0, 500.0) if not high_errors else rng.gauss(6500.0, 800.0)
    wpm = rng.gauss(110.0, 15.0) if not high_errors else rng.gauss(62.0, 12.0)

    subs = rng.randint(0, 1) if not high_errors else rng.randint(2, 5)
    omiss = rng.randint(0, 1) if not high_errors else rng.randint(1, 4)
    inserts = rng.randint(0, 1) if not high_errors else rng.randint(1, 3)
    reps = rng.randint(0, 1) if not high_errors else rng.randint(1, 3)

    tokens = rng.randint(8, 16)
    unique_tokens = min(tokens, int(tokens * rng.uniform(0.75, 1.0)))
    type_token_ratio = unique_tokens / tokens if tokens else 1.0
    text_repetition = reps

    error_rate = (subs + omiss + inserts) / max(1, tokens)
    pause_count = rng.randint(1, 3) if not high_errors else rng.randint(4, 8)
    mean_pause_ms = rng.gauss(450.0, 60.0) if not high_errors else rng.gauss(850.0, 120.0)
    med_pause_ms = mean_pause_ms - rng.uniform(20.0, 60.0)
    pause_var = rng.gauss(8000.0, 1200.0) if not high_errors else rng.gauss(32000.0, 4500.0)

    values: dict[str, float | int] = {
        "speech_available": 1,
        "speech_reading_duration_ms": duration_ms,
        "speech_words_per_minute": wpm,
        "speech_substitution_count": subs,
        "speech_omission_count": omiss,
        "speech_insertion_count": inserts,
        "speech_repetition_count": reps,
        "speech_error_rate": error_rate,
        "speech_pause_count": pause_count,
        "speech_mean_pause_duration_ms": mean_pause_ms,
        "speech_median_pause_duration_ms": med_pause_ms,
        "speech_pause_variability_ms2": pause_var,
        "text_token_count": tokens,
        "text_unique_token_count": unique_tokens,
        "text_type_token_ratio": type_token_ratio,
        "text_repetition_count": text_repetition,
    }

    for name in SPEECH_FEATURE_NAMES:
        records[name] = make_feature_record(name, values[name], available=True, schema_version=schema_version)
    return records

