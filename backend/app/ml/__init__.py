"""Research-safe feature engineering and baseline ML infrastructure."""

FEATURE_SCHEMA_VERSION = "1.0"
FEATURE_EXTRACTOR_VERSION = "1.0"

# Speech ML submodule
from .speech import (
    AudioPreprocessor,
    AudioConfig,
    SpeechManifestEntry,
    WhisperModelConfig,
    WhisperModelManager,
    HuggingFaceWhisperProvider,
    WhisperFineTuneConfig,
    run_finetune,
    EvaluationConfig,
    evaluate_model,
    SpeechExperimentConfig,
    create_experiment_config,
)

__all__ = [
    "FEATURE_SCHEMA_VERSION",
    "FEATURE_EXTRACTOR_VERSION",
    "AudioPreprocessor",
    "AudioConfig",
    "SpeechManifestEntry",
    "WhisperModelConfig",
    "WhisperModelManager",
    "HuggingFaceWhisperProvider",
    "WhisperFineTuneConfig",
    "run_finetune",
    "EvaluationConfig",
    "evaluate_model",
    "SpeechExperimentConfig",
    "create_experiment_config",
]
