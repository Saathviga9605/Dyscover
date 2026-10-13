"""Structured trial and session interaction simulator.

Generates realistic game interaction observations consistent with Dyscover's
canonical schemas, task structures, and documented simulation assumptions.
"""

from __future__ import annotations

from random import Random
from statistics import mean, median, pvariance
from typing import Any

from app.ml.feature_registry import REGISTRY_BY_NAME
from .games import (
    GAME_DIFFICULTY_LEVELS,
    GAME_DOMAINS,
    validate_game_language_pair,
)
from .modalities import (
    make_feature_record,
    simulate_gaze_features,
    simulate_speech_features,
)
from .taxonomy import PROFILES, ScenarioProfile

BEHAVIORAL_FEATURE_NAMES = (
    "overall_accuracy",
    "incorrect_response_rate",
    "mean_reaction_time_ms",
    "median_reaction_time_ms",
    "reaction_time_variance_ms2",
    "mean_hesitation_time_ms",
    "total_error_count",
    "completion_rate",
    "pause_count",
    "hint_count",
)


def simulate_trial_sequence(
    rng: Random,
    scenario: str,
    game: str,
    target_trial_count: int,
    difficulty: int = 1,
) -> tuple[list[dict[str, Any]], bool]:
    """Simulate trial-by-trial responses under explicit simulation assumptions."""
    profile = PROFILES[scenario]
    completed_trials: list[dict[str, Any]] = []

    # Insufficient observations scenario simulates premature session abandonment
    if scenario == "insufficient_observations":
        actual_count = rng.randint(1, max(1, target_trial_count // 3))
        completed_session = False
    else:
        actual_count = target_trial_count
        completed_session = True

    # Base target accuracy for this scenario
    base_acc = rng.uniform(*profile.target_accuracy_range)

    # Specific profile adjustments by game type
    if scenario == "working_memory_task_difficulty" and game == "sequence-quest":
        # Working memory task degrades with difficulty and sequence length
        base_acc = max(0.20, base_acc - 0.12 * difficulty)
    elif scenario == "repeated_symbol_confusions" and game in {"letter-detective", "mirror-match"}:
        # Symbol discrimination tasks have elevated confusion
        base_acc = max(0.25, base_acc - 0.20)

    # Base reaction time scaled by difficulty
    base_rt = profile.mean_reaction_time_ms * (1.0 + 0.05 * (difficulty - 1))
    rt_var = profile.reaction_time_variance_ms2

    last_was_error = False
    for trial_idx in range(actual_count):
        # Simulation Assumption: Trial-order fatigue effect
        # Reaction time increases slightly (+2-4% per trial) as session progresses
        fatigue_multiplier = 1.0 + 0.03 * trial_idx

        # Response correctness
        is_correct = rng.random() < base_acc
        score = 1.0 if is_correct else 0.0

        # Simulation Assumption: Error recovery hesitation
        # Following an incorrect response, hesitation is elevated on the subsequent trial
        hesitation = profile.hesitation_mean_ms + rng.gauss(0, 20.0)
        if last_was_error:
            hesitation += rng.uniform(80.0, 180.0)
        hesitation = max(10.0, hesitation)

        # Reaction time for this trial
        rt_std = max(10.0, (rt_var ** 0.5))
        rt = max(150.0, rng.gauss(base_rt * fatigue_multiplier, rt_std))

        error_count = 0 if is_correct else (1 if rng.random() < 0.8 else 2)

        trial_record = {
            "trial_index": trial_idx,
            "correctness": is_correct,
            "score": score,
            "reaction_time_ms": rt,
            "hesitation_time_ms": hesitation,
            "error_count": error_count,
            "difficulty": difficulty,
        }
        completed_trials.append(trial_record)
        last_was_error = not is_correct

    return completed_trials, completed_session


def simulate_session(
    rng: Random,
    subject_id: str,
    session_id: str,
    scenario: str,
    game: str,
    language: str,
    trials_per_session: int = 5,
    difficulty: int = 2,
    modality_available: bool = True,
    gaze_available: bool | None = None,
    speech_available: bool | None = None,
    schema_version: str = "1.0",
) -> dict[str, Any]:
    """Generate a single simulated session with all 40 canonical features and metadata."""
    validate_game_language_pair(game, language)
    profile = PROFILES[scenario]

    # Run trial simulation
    trials, is_complete = simulate_trial_sequence(rng, scenario, game, trials_per_session, difficulty)

    # Compute aggregate behavioral metrics
    correctness_vals = [t["correctness"] for t in trials]
    rt_vals = [t["reaction_time_ms"] for t in trials]
    hesitation_vals = [t["hesitation_time_ms"] for t in trials]
    error_counts = [t["error_count"] for t in trials]

    acc = mean(correctness_vals) if correctness_vals else None
    incorrect_rate = (1.0 - acc) if acc is not None else None
    mean_rt = mean(rt_vals) if rt_vals else None
    med_rt = median(rt_vals) if rt_vals else None
    var_rt = pvariance(rt_vals) if len(rt_vals) > 1 else (0.0 if len(rt_vals) == 1 else None)
    mean_hes = mean(hesitation_vals) if hesitation_vals else None
    total_errors = sum(error_counts)
    comp_rate = len(trials) / trials_per_session if trials_per_session > 0 else 0.0

    # Engagement events
    is_attention = scenario == "attention_variability"
    pause_cnt = rng.randint(3, 7) if is_attention else (rng.randint(0, 1) if scenario == "consistent_responses" else rng.randint(0, 3))
    hint_cnt = rng.randint(2, 5) if is_attention else (0 if scenario == "consistent_responses" else rng.randint(0, 2))

    features: dict[str, dict[str, Any]] = {
        "overall_accuracy": make_feature_record("overall_accuracy", acc, available=acc is not None, schema_version=schema_version),
        "incorrect_response_rate": make_feature_record("incorrect_response_rate", incorrect_rate, available=incorrect_rate is not None, schema_version=schema_version),
        "mean_reaction_time_ms": make_feature_record("mean_reaction_time_ms", mean_rt, available=mean_rt is not None, schema_version=schema_version),
        "median_reaction_time_ms": make_feature_record("median_reaction_time_ms", med_rt, available=med_rt is not None, schema_version=schema_version),
        "reaction_time_variance_ms2": make_feature_record("reaction_time_variance_ms2", var_rt, available=var_rt is not None, schema_version=schema_version),
        "mean_hesitation_time_ms": make_feature_record("mean_hesitation_time_ms", mean_hes, available=mean_hes is not None, schema_version=schema_version),
        "total_error_count": make_feature_record("total_error_count", total_errors, available=True, schema_version=schema_version),
        "completion_rate": make_feature_record("completion_rate", comp_rate, available=True, schema_version=schema_version),
        "pause_count": make_feature_record("pause_count", pause_cnt, available=True, schema_version=schema_version),
        "hint_count": make_feature_record("hint_count", hint_cnt, available=True, schema_version=schema_version),
    }

    # Modality simulation
    effective_gaze = gaze_available if gaze_available is not None else modality_available
    effective_speech = speech_available if speech_available is not None else modality_available

    gaze_features = simulate_gaze_features(rng, effective_gaze, scenario, schema_version)
    features.update(gaze_features)

    speech_features = simulate_speech_features(rng, effective_speech, scenario, game, schema_version)
    features.update(speech_features)

    return {
        "subject_id": subject_id,
        "session_id": session_id,
        "game_id": game,
        "domain": GAME_DOMAINS[game],
        "language": language,
        "difficulty": difficulty,
        "target": scenario,
        "scenario": scenario,
        "synthetic": True,
        "intended_use": "simulator_profile_classification",
        "clinical_use": "prohibited",
        "simulator_version": "1.0",
        "feature_schema_version": schema_version,
        "completed": is_complete,
        "completed_trials": len(trials),
        "trials_requested": trials_per_session,
        "features": features,
    }

