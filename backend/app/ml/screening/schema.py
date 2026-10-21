"""Screening target and approved feature schema.

The target is deliberately *not* "has dyslexia". Dyscover is a screening aid:
a model may only estimate whether a child's observed activity pattern resembles
that of children who, in an independent reference assessment, showed reading
difficulties that warranted further assessment. Diagnosis remains a qualified
professional's task.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

TARGET_ID = "elevated_reading_difficulty_risk_v1"
TARGET_DEFINITION = (
    "Elevated risk of reading difficulties warranting further assessment: the reference "
    "label is positive when a standardised reading/phonological assessment administered "
    "independently of Dyscover, and interpreted by a qualified specialist, recommended "
    "further assessment or reading support. It is not a dyslexia diagnosis."
)

SCREENING_SCHEMA_VERSION = "screening-1.0"

# Visual-game domains that every eligible assessment can produce.
VISUAL_DOMAINS = (
    "visual-symbol-discrimination",
    "orthographic-recognition",
    "working-memory",
    "attention-visual-search",
)


@dataclass(frozen=True)
class ScreeningFeature:
    name: str
    description: str
    minimum: float | None
    maximum: float | None
    modality: str
    required: bool


# Rates and timing summaries only. Excluded on purpose: child/assessment/subject IDs,
# game IDs, language codes, timestamps, absolute counts that scale with session length,
# and any field derived from a label or from simulator profile parameters.
SCREENING_FEATURES: tuple[ScreeningFeature, ...] = (
    ScreeningFeature("overall_accuracy", "Proportion of scored trials answered correctly", 0, 1, "behavior", True),
    ScreeningFeature("median_reaction_time_ms", "Median response time on scored trials", 0, 600_000, "behavior", True),
    ScreeningFeature("reaction_time_variance_ms2", "Variance of response times", 0, None, "behavior", False),
    ScreeningFeature("mean_hesitation_time_ms", "Mean hesitation before responding", 0, 600_000, "behavior", False),
    ScreeningFeature("completion_rate", "Completed trials divided by started trials", 0, 1, "behavior", True),
    *(
        ScreeningFeature(f"domain_{domain}_accuracy", f"Accuracy in {domain.replace('-', ' ')} activities", 0, 1, "behavior", False)
        for domain in VISUAL_DOMAINS
    ),
    ScreeningFeature("speech_error_rate", "Reading-aloud alignment errors per expected word", 0, 1, "speech", False),
    ScreeningFeature("speech_words_per_minute", "Recognised words per minute while reading aloud", 0, 400, "speech", False),
    ScreeningFeature("gaze_regression_count", "Right-to-left eye movements (when eye tracking ran)", 0, None, "gaze", False),
    ScreeningFeature("gaze_mean_fixation_duration_ms", "Mean fixation duration (when eye tracking ran)", 0, 10_000, "gaze", False),
)
FEATURE_NAMES: tuple[str, ...] = tuple(feature.name for feature in SCREENING_FEATURES)
_BY_NAME = {feature.name: feature for feature in SCREENING_FEATURES}

# Identifier-like or label-like names that must never become model inputs.
FORBIDDEN_FEATURE_FRAGMENTS = ("id", "label", "target", "profile", "scenario", "diagnos", "risk", "timestamp", "name")


@dataclass
class FeatureValidation:
    vector: dict[str, float | None]
    missing_required: list[str]
    invalid: list[str]
    missing_optional: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing_required and not self.invalid


def _plain_value(item: Any) -> Any:
    if isinstance(item, dict):
        return item.get("value") if item.get("available", True) else None
    return item


def validate_features(raw: dict[str, Any]) -> FeatureValidation:
    """Map extracted features onto the schema. Missing stays ``None`` (never 0)."""
    vector: dict[str, float | None] = {}
    missing_required: list[str] = []
    missing_optional: list[str] = []
    invalid: list[str] = []
    for feature in SCREENING_FEATURES:
        value = _plain_value(raw.get(feature.name))
        if value is None:
            vector[feature.name] = None
            (missing_required if feature.required else missing_optional).append(feature.name)
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            invalid.append(feature.name)
            vector[feature.name] = None
            continue
        value = float(value)
        if (feature.minimum is not None and value < feature.minimum) or (feature.maximum is not None and value > feature.maximum):
            invalid.append(feature.name)
            vector[feature.name] = None
            continue
        vector[feature.name] = value
    return FeatureValidation(vector, missing_required, invalid, missing_optional)


def assert_schema_is_leak_free(names: tuple[str, ...] = FEATURE_NAMES) -> None:
    for name in names:
        lowered = name.lower()
        for fragment in FORBIDDEN_FEATURE_FRAGMENTS:
            # "id" must match as a token, not inside e.g. "accuracy".
            tokens = lowered.replace("-", "_").split("_")
            if (fragment == "id" and "id" in tokens) or (fragment != "id" and fragment in lowered):
                raise ValueError(f"Feature {name!r} looks like an identifier or label ({fragment!r})")


assert_schema_is_leak_free()
