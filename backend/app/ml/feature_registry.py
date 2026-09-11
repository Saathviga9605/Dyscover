from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    description: str
    domain: str
    unit: str
    datatype: Literal["float", "integer"]
    minimum: float | None
    maximum: float | None
    aggregation: str
    modality: Literal["behavior", "gaze", "speech", "text"]
    required: bool = False
    version: str = "1.0"


FEATURE_REGISTRY: tuple[FeatureDefinition, ...] = (
    FeatureDefinition("overall_accuracy", "Accuracy across completed trials", "accuracy", "proportion", "float", 0, 1, "mean", "behavior"),
    FeatureDefinition("incorrect_response_rate", "Incorrect response proportion", "accuracy", "proportion", "float", 0, 1, "mean", "behavior"),
    FeatureDefinition("mean_reaction_time_ms", "Mean measured reaction time", "timing", "milliseconds", "float", 0, None, "mean", "behavior"),
    FeatureDefinition("median_reaction_time_ms", "Median measured reaction time", "timing", "milliseconds", "float", 0, None, "median", "behavior"),
    FeatureDefinition("reaction_time_variance_ms2", "Reaction-time variance", "timing", "milliseconds_squared", "float", 0, None, "population_variance", "behavior"),
    FeatureDefinition("mean_hesitation_time_ms", "Mean hesitation duration", "hesitation", "milliseconds", "float", 0, None, "mean", "behavior"),
    FeatureDefinition("total_error_count", "Total recorded trial errors", "errors", "count", "integer", 0, None, "sum", "behavior"),
    FeatureDefinition("completion_rate", "Completed trials divided by trials", "completion", "proportion", "float", 0, 1, "ratio", "behavior"),
    FeatureDefinition("pause_count", "Session pause events", "engagement", "count", "integer", 0, None, "count", "behavior"),
    FeatureDefinition("hint_count", "Hint-use events", "engagement", "count", "integer", 0, None, "count", "behavior"),
    FeatureDefinition("gaze_available", "Whether gaze-derived data exists", "gaze", "boolean", "integer", 0, 1, "availability", "gaze"),
)

REGISTRY_BY_NAME = {feature.name: feature for feature in FEATURE_REGISTRY}

def feature_definitions() -> list[dict[str, object]]:
    return [feature.__dict__.copy() for feature in FEATURE_REGISTRY]
