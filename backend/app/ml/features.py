from collections import Counter, defaultdict
from statistics import mean, median, pvariance
from typing import Any

from . import FEATURE_EXTRACTOR_VERSION, FEATURE_SCHEMA_VERSION
from .validation import validate_trials
from .feature_registry import REGISTRY_BY_NAME

_GAZE_FEATURE_NAMES = (
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

_SPEECH_MEAN_FEATURES = (
    "speech_reading_duration_ms",
    "speech_words_per_minute",
    "speech_error_rate",
    "speech_mean_pause_duration_ms",
    "speech_median_pause_duration_ms",
    "speech_pause_variability_ms2",
    "text_token_count",
    "text_unique_token_count",
    "text_type_token_ratio",
)

_SPEECH_SUM_FEATURES = (
    "speech_substitution_count",
    "speech_omission_count",
    "speech_insertion_count",
    "speech_repetition_count",
    "speech_pause_count",
    "text_repetition_count",
)


def _feature(name: str, value: float | int | None, unit: str, source: str, domain: str, available: bool = True) -> dict[str, Any]:
    definition = REGISTRY_BY_NAME.get(name)
    return {"name": name, "value": value, "unit": unit, "source": source, "domain": domain, "available": available, "status": "available" if available else "missing", "modality": definition.modality if definition else "behavior", "extraction_version": FEATURE_EXTRACTOR_VERSION, "calculation_version": FEATURE_SCHEMA_VERSION}


def extract_session_features(session: Any, games: list[Any], trials: list[Any], events: list[Any], gaze_features: dict[str, float | int | None] | None = None, speech_sessions: list[dict[str, Any]] | None = None) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    quality = validate_trials(trials, events)
    completed = [trial for trial in trials if trial.completed_at]
    correctness = [trial.correctness for trial in completed if trial.correctness is not None]
    reactions = [trial.reaction_time_ms for trial in completed if trial.reaction_time_ms is not None]
    hesitations = [trial.hesitation_time_ms for trial in completed if trial.hesitation_time_ms is not None]
    by_domain: dict[str, list[Any]] = defaultdict(list)
    by_game: dict[str, list[Any]] = defaultdict(list)
    for trial in completed:
        by_domain[trial.domain or "unknown"].append(trial)
        game_id = next((game.game_id for game in games if game.id == trial.game_session_id), "unknown")
        by_game[game_id].append(trial)
    features: dict[str, dict[str, Any]] = {}
    features["overall_accuracy"] = _feature("overall_accuracy", mean(correctness) if correctness else None, "proportion", "behavior", "accuracy", bool(correctness))
    features["incorrect_response_rate"] = _feature("incorrect_response_rate", 1 - mean(correctness) if correctness else None, "proportion", "behavior", "accuracy", bool(correctness))
    features["mean_reaction_time_ms"] = _feature("mean_reaction_time_ms", mean(reactions) if reactions else None, "milliseconds", "behavior", "timing", bool(reactions))
    features["median_reaction_time_ms"] = _feature("median_reaction_time_ms", median(reactions) if reactions else None, "milliseconds", "behavior", "timing", bool(reactions))
    features["reaction_time_variance_ms2"] = _feature("reaction_time_variance_ms2", pvariance(reactions) if len(reactions) > 1 else None, "milliseconds_squared", "behavior", "timing", len(reactions) > 1)
    features["mean_hesitation_time_ms"] = _feature("mean_hesitation_time_ms", mean(hesitations) if hesitations else None, "milliseconds", "behavior", "hesitation", bool(hesitations))
    features["total_error_count"] = _feature("total_error_count", sum(trial.error_count for trial in completed), "count", "behavior", "errors", bool(completed))
    features["completion_rate"] = _feature("completion_rate", len(completed) / len(trials) if trials else None, "proportion", "behavior", "completion", bool(trials))
    features["pause_count"] = _feature("pause_count", sum(event.event_type in {"SESSION_PAUSED", "PAUSED"} for event in events), "count", "events", "engagement", True)
    features["hint_count"] = _feature("hint_count", sum(event.event_type in {"HINT_USED", "HINT_REQUESTED"} for event in events), "count", "events", "engagement", True)
    for domain, domain_trials in by_domain.items():
        domain_correct = [trial.correctness for trial in domain_trials if trial.correctness is not None]
        features[f"domain_{domain}_accuracy"] = _feature(f"domain_{domain}_accuracy", mean(domain_correct) if domain_correct else None, "proportion", domain, "domain_performance", bool(domain_correct))
    for game_id, game_trials in by_game.items():
        game_correct = [trial.correctness for trial in game_trials if trial.correctness is not None]
        game_reactions = [trial.reaction_time_ms for trial in game_trials if trial.reaction_time_ms is not None]
        features[f"game_{game_id}_accuracy"] = _feature(f"game_{game_id}_accuracy", mean(game_correct) if game_correct else None, "proportion", game_id, "accuracy", bool(game_correct))
        features[f"game_{game_id}_mean_reaction_time_ms"] = _feature(f"game_{game_id}_mean_reaction_time_ms", mean(game_reactions) if game_reactions else None, "milliseconds", game_id, "timing", bool(game_reactions))
    _append_gaze_features(features, gaze_features or {})
    _append_speech_features(features, speech_sessions or [])
    quality["feature_count"] = len(features)
    quality["available_feature_count"] = sum(item["available"] for item in features.values())
    quality["feature_schema_version"] = FEATURE_SCHEMA_VERSION
    quality["missing_feature_percentage"] = {name: 0.0 if item["available"] else 100.0 for name, item in features.items()}
    quality["unknown_feature_names"] = [name for name in features if name not in REGISTRY_BY_NAME]
    return features, quality


def _append_gaze_features(features: dict[str, dict[str, Any]], gaze: dict[str, float | int | None]) -> None:
    definition = REGISTRY_BY_NAME.get("gaze_available")
    present = any(value is not None for value in gaze.values())
    if present:
        gaze_features = {name: value for name, value in gaze.items() if value is not None}
        features["gaze_available"] = {"name": "gaze_available", "value": 1, "unit": "boolean", "source": "gaze", "domain": "gaze", "available": True, "status": "available", "modality": definition.modality, "extraction_version": FEATURE_EXTRACTOR_VERSION, "calculation_version": FEATURE_SCHEMA_VERSION}
        for name, value in gaze_features.items():
            if name not in REGISTRY_BY_NAME or value is None:
                continue
            item = REGISTRY_BY_NAME[name]
            features[name] = _feature(name, value, item.unit, "gaze", item.domain, True)
    else:
        features["gaze_available"] = _feature("gaze_available", None, "boolean", "gaze", "gaze", False)
        for name in _GAZE_FEATURE_NAMES:
            item = REGISTRY_BY_NAME.get(name)
            features[name] = _feature(name, None, item.unit if item else "", "gaze", item.domain if item else "gaze", False)


def _append_speech_features(features: dict[str, dict[str, Any]], speech_sessions: list[dict[str, Any]]) -> None:
    per_trial_features = [session.get("features", {}) for session in speech_sessions if isinstance(session.get("features"), dict)]
    available_values: dict[str, list[float]] = {}
    for session_features in per_trial_features:
        for name, item in session_features.items():
            if isinstance(item, dict) and item.get("available") and isinstance(item.get("value"), (int, float)):
                available_values.setdefault(name, []).append(float(item["value"]))
    has_sessions = bool(per_trial_features)
    if has_sessions:
        features["speech_available"] = _feature("speech_available", 1 if any(available_values.values()) else 0, "boolean", "speech", "speech", True)
    else:
        features["speech_available"] = _feature("speech_available", None, "boolean", "speech", "speech", False)

    for name in (*_SPEECH_MEAN_FEATURES, *_SPEECH_SUM_FEATURES):
        item = REGISTRY_BY_NAME.get(name)
        values = available_values.get(name)
        aggregate = None
        if values:
            aggregate = sum(values) if name in _SPEECH_SUM_FEATURES else mean(values)
        features[name] = _feature(name, aggregate, item.unit if item else "", item.domain if item else "speech", item.domain if item else "speech", bool(values))
