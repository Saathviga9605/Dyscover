from enum import StrEnum


class AssessmentDomain(StrEnum):
    VISUAL_SYMBOL_DISCRIMINATION = "visual-symbol-discrimination"
    ORTHOGRAPHIC_RECOGNITION = "orthographic-recognition"
    PHONOLOGICAL_AWARENESS = "phonological-awareness"
    WORKING_MEMORY = "working-memory"
    SEQUENCING = "sequencing"
    ATTENTION_VISUAL_SEARCH = "attention-visual-search"
    READING_FLUENCY = "reading-fluency"
    INTERACTION_BEHAVIOR = "interaction-behavior"


RESEARCH_FEATURE_NAMES = (
    "mean_fixation_duration",
    "max_fixation_duration",
    "fixation_count",
    "target_fixation_duration",
    "distractor_fixation_duration",
    "distractor_target_ratio",
    "ttff",
    "fixation_switches",
    "reaction_time",
    "hesitation_time",
    "saccade_variance",
    "regression_count",
    "scanpath_entropy",
    "horizontal_saccade_bias",
)
