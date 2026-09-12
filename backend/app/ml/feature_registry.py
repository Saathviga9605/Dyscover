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
    FeatureDefinition("gaze_sample_count", "Raw gaze sample count", "gaze", "count", "integer", 0, None, "sum", "gaze"),
    FeatureDefinition("gaze_fixation_count", "Detected fixation count", "gaze", "count", "integer", 0, None, "sum", "gaze"),
    FeatureDefinition("gaze_mean_fixation_duration_ms", "Mean fixation duration", "gaze", "milliseconds", "float", 0, None, "weighted_mean", "gaze"),
    FeatureDefinition("gaze_max_fixation_duration_ms", "Longest fixation duration", "gaze", "milliseconds", "float", 0, None, "max", "gaze"),
    FeatureDefinition("gaze_target_fixation_time_ms", "Time spent fixating target regions", "gaze", "milliseconds", "float", 0, None, "sum", "gaze"),
    FeatureDefinition("gaze_distractor_fixation_time_ms", "Time spent fixating competing regions", "gaze", "milliseconds", "float", 0, None, "sum", "gaze"),
    FeatureDefinition("gaze_time_to_first_target_fixation_ms", "Latency to first target fixation", "gaze", "milliseconds", "float", 0, None, "mean", "gaze"),
    FeatureDefinition("gaze_fixation_switch_count", "Regions alternated between", "gaze", "count", "integer", 0, None, "sum", "gaze"),
    FeatureDefinition("gaze_regression_count", "Right-to-left saccade count", "gaze", "count", "integer", 0, None, "sum", "gaze"),
    FeatureDefinition("gaze_saccade_variance_ms2", "Saccade-interval variance", "gaze", "milliseconds_squared", "float", 0, None, "mean", "gaze"),
    FeatureDefinition("gaze_scanpath_entropy", "Scanpath region-label entropy", "gaze", "bits", "float", 0, None, "mean", "gaze"),
    FeatureDefinition("gaze_horizontal_saccade_bias", "Horizontal saccade directional bias", "gaze", "proportion", "float", -1, 1, "mean", "gaze"),
    FeatureDefinition("gaze_coverage_ratio", "Distinct regions observed over configured regions", "gaze", "proportion", "float", 0, 1, "weighted_mean", "gaze"),
    FeatureDefinition("speech_available", "Whether speech-derived data exists", "speech", "boolean", "integer", 0, 1, "availability", "speech"),
    FeatureDefinition("speech_reading_duration_ms", "Recorded reading duration when available", "fluency", "milliseconds", "float", 0, None, "observed", "speech"),
    FeatureDefinition("speech_words_per_minute", "Recognized words divided by measured duration", "fluency", "words_per_minute", "float", 0, None, "ratio", "speech"),
    FeatureDefinition("speech_substitution_count", "Expected words replaced in alignment", "reading_errors", "count", "integer", 0, None, "count", "speech"),
    FeatureDefinition("speech_omission_count", "Expected words absent from transcript", "reading_errors", "count", "integer", 0, None, "count", "speech"),
    FeatureDefinition("speech_insertion_count", "Additional transcript words", "reading_errors", "count", "integer", 0, None, "count", "speech"),
    FeatureDefinition("speech_repetition_count", "Repeated recognized words", "reading_errors", "count", "integer", 0, None, "count", "speech"),
    FeatureDefinition("speech_error_rate", "Alignment errors divided by expected words", "reading_errors", "proportion", "float", 0, 1, "ratio", "speech"),
    FeatureDefinition("speech_pause_count", "Pauses meeting configured threshold", "pauses", "count", "integer", 0, None, "count", "speech"),
    FeatureDefinition("speech_mean_pause_duration_ms", "Mean configured pause duration", "pauses", "milliseconds", "float", 0, None, "mean", "speech"),
    FeatureDefinition("speech_median_pause_duration_ms", "Median configured pause duration", "pauses", "milliseconds", "float", 0, None, "median", "speech"),
    FeatureDefinition("speech_pause_variability_ms2", "Pause duration variance", "pauses", "milliseconds_squared", "float", 0, None, "population_variance", "speech"),
    FeatureDefinition("text_token_count", "Transcript token count", "lexical", "count", "integer", 0, None, "count", "text"),
    FeatureDefinition("text_unique_token_count", "Unique transcript token count", "lexical", "count", "integer", 0, None, "count", "text"),
    FeatureDefinition("text_type_token_ratio", "Unique tokens divided by total tokens", "lexical", "proportion", "float", 0, 1, "ratio", "text"),
    FeatureDefinition("text_repetition_count", "Repeated transcript token count", "lexical", "count", "integer", 0, None, "sum", "text"),
)

REGISTRY_BY_NAME = {feature.name: feature for feature in FEATURE_REGISTRY}

def feature_definitions() -> list[dict[str, object]]:
    return [feature.__dict__.copy() for feature in FEATURE_REGISTRY]
