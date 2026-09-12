"""Deterministic, non-clinical gaze feature extraction.

These functions are pure: they summarize stored samples/fixations into the
canonical ``gaze_*`` feature names registered in ``app.ml.feature_registry``.
Missing measurements are represented as ``None`` (never as zero) so that
availability is explicit and observable.  There is deliberately no
thresholding, no scoring, and no inference.
"""

import math
from statistics import mean, pvariance
from typing import Any

from app.ml.feature_registry import REGISTRY_BY_NAME

DISTRACTOR_LABELS = {"target", "distractor", "option", "instruction"}
DEFAULT_REGION_LABELS = ("target", "distractor", "option", "instruction")
JITTER_RADIUS = 40.0


def _labeled(fixations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [fixation for fixation in fixations if fixation.get("target_type")]


def analyze_fixations(sample_count: int, fixations: list[dict[str, Any]], region_labels: list[str] | None = None) -> dict[str, float | int | None]:
    """Summarize one trial's gaze data into canonical feature values."""
    labels = tuple(region_labels) if region_labels else DEFAULT_REGION_LABELS
    ordered = sorted(fixations, key=lambda item: item.get("start_epoch_ms", 0.0))
    durations = [fixation.get("duration_ms", 0) for fixation in ordered]
    count = len(ordered)
    result: dict[str, float | int | None] = {
        "gaze_sample_count": sample_count,
        "gaze_fixation_count": count,
        "gaze_mean_fixation_duration_ms": round(mean(durations)) if durations else None,
        "gaze_max_fixation_duration_ms": max(durations) if durations else None,
        "gaze_target_fixation_time_ms": sum(d for exposure in ordered if (label := exposure.get("target_type")) == "target" for d in [exposure.get("duration_ms", 0)]) if any(fixation.get("target_type") == "target" for fixation in ordered) else None,
        "gaze_distractor_fixation_time_ms": sum(exposure.get("duration_ms", 0) for exposure in ordered if exposure.get("target_type") in DISTRACTOR_LABELS and exposure.get("target_type") != "target") if count > 0 else None,
        "gaze_time_to_first_target_fixation_ms": _time_to_first_target(ordered),
        "gaze_fixation_switch_count": _switch_count(ordered) if count > 1 else (0 if count == 1 else None),
        "gaze_regression_count": _regression_count(ordered) if count > 1 else (0 if count == 1 else None),
        "gaze_saccade_variance_ms2": _saccade_variance(ordered),
        "gaze_scanpath_entropy": _scanpath_entropy(ordered),
        "gaze_horizontal_saccade_bias": _horizontal_bias(ordered) if count > 1 else None,
        "gaze_coverage_ratio": _coverage_ratio(ordered, labels) if count > 0 else None,
    }
    return result


def aggregate_gaze_features(batches: list[dict[str, Any]]) -> dict[str, float | int | None]:
    """Combine per-trial summaries into session-level canonical features."""
    available: dict[str, list[float]] = {}
    for batch in batches:
        for name, value in batch.items():
            if value is None:
                continue
            available.setdefault(name, []).append(float(value))
    if not batches:
        return {name: None for name in ("gaze_sample_count", "gaze_fixation_count", "gaze_mean_fixation_duration_ms", "gaze_max_fixation_duration_ms", "gaze_target_fixation_time_ms", "gaze_distractor_fixation_time_ms", "gaze_time_to_first_target_fixation_ms", "gaze_fixation_switch_count", "gaze_regression_count", "gaze_saccade_variance_ms2", "gaze_scanpath_entropy", "gaze_horizontal_saccade_bias", "gaze_coverage_ratio")}

    sums = {name: sum(values) for name, values in available.items()}
    counts = {name: len(values) for name, values in available.items()}
    total_fixations = sum(round(value) for value in available.get("gaze_fixation_count", []))

    def _mean_of(name: str) -> float | None:
        values = available.get(name)
        if not values:
            return None
        weight = [round(a) for a in available.get("gaze_fixation_count", [])]
        if len(values) == len(weight) and sum(weight) and name in {"gaze_mean_fixation_duration_ms", "gaze_coverage_ratio"}:
            return round(sum(value * weight[index] for index, value in enumerate(values)) / sum(weight))
        return round(mean(values), 2) if name not in {"gaze_mean_fixation_duration_ms", "gaze_coverage_ratio"} else round(mean(values))

    result: dict[str, float | int | None] = {
        "gaze_sample_count": sums.get("gaze_sample_count"),
        "gaze_fixation_count": total_fixations if total_fixations else None,
        "gaze_mean_fixation_duration_ms": _mean_of("gaze_mean_fixation_duration_ms"),
        "gaze_max_fixation_duration_ms": sums.get("gaze_max_fixation_duration_ms") if counts.get("gaze_max_fixation_duration_ms", 0) == 1 else max(available.get("gaze_max_fixation_duration_ms", [0])) if available.get("gaze_max_fixation_duration_ms") else None,
        "gaze_target_fixation_time_ms": sums.get("gaze_target_fixation_time_ms"),
        "gaze_distractor_fixation_time_ms": sums.get("gaze_distractor_fixation_time_ms"),
        "gaze_time_to_first_target_fixation_ms": _mean_of("gaze_time_to_first_target_fixation_ms"),
        "gaze_fixation_switch_count": sums.get("gaze_fixation_switch_count"),
        "gaze_regression_count": sums.get("gaze_regression_count"),
        "gaze_saccade_variance_ms2": _mean_of("gaze_saccade_variance_ms2"),
        "gaze_scanpath_entropy": _mean_of("gaze_scanpath_entropy"),
        "gaze_horizontal_saccade_bias": _mean_of("gaze_horizontal_saccade_bias"),
        "gaze_coverage_ratio": _mean_of("gaze_coverage_ratio"),
    }
    return result


def _time_to_first_target(fixations: list[dict[str, Any]]) -> float | int | None:
    target = [fixation for fixation in fixations if fixation.get("target_type") == "target"]
    if not target or not fixations:
        return None
    first = fixations[0].get("start_epoch_ms")
    if first is None:
        return None
    return round(min(item["start_epoch_ms"] for item in target) - first)


def _switch_count(fixations: list[dict[str, Any]]) -> int:
    return sum(1 for previous, current in zip(fixations, fixations[1:]) if previous.get("target_type") != current.get("target_type") and previous.get("target_type") and current.get("target_type"))


def _regression_count(fixations: list[dict[str, Any]]) -> int:
    return sum(1 for previous, current in zip(fixations, fixations[1:]) if current.get("x", 0.0) < previous.get("x", 0.0) and abs((current.get("y", 0.0)) - previous.get("y", 0.0)) <= JITTER_RADIUS)


def _saccade_variance(fixations: list[dict[str, Any]]) -> float | None:
    intervals = [group[1].get("start_epoch_ms", 0.0) - group[0].get("end_epoch_ms", 0.0) for group in zip(fixations, fixations[1:])]
    intervals = [value for value in intervals if value >= 0]
    if len(intervals) < 2:
        return None
    return round(pvariance(intervals), 2)


def _scanpath_entropy(fixations: list[dict[str, Any]]) -> float | None:
    labels = [fixation.get("target_type") for fixation in _labeled(fixations)]
    if len(labels) < 2:
        return None
    from collections import Counter

    counts = Counter(labels)
    total = len(labels)
    entropy = -sum((count / total) * math.log2(count / total) for count in counts.values())
    return round(entropy, 4)


def _horizontal_bias(fixations: list[dict[str, Any]]) -> float | None:
    horizontal = [current.get("x", 0.0) - previous.get("x", 0.0) for previous, current in zip(fixations, fixations[1:])]
    vertical = [current.get("y", 0.0) - previous.get("y", 0.0) for previous, current in zip(fixations, fixations[1:])]
    total = [math.hypot(dx, dy) for dx, dy in zip(horizontal, vertical)]
    if not total or sum(total) == 0:
        return None
    return round(sum(dx for dx in horizontal) / sum(total), 4)


def _coverage_ratio(fixations: list[dict[str, Any]], labels: list[str]) -> float | None:
    present = {fixation.get("target_type") for fixation in _labeled(fixations)}
    covered = present & set(labels)
    if not labels:
        return None
    return round(len(covered) / len(labels), 4)


def feature_defined(name: str) -> bool:
    return name in REGISTRY_BY_NAME