"""Speech ML module for Dyscover."""

from .audio import AudioPreprocessor, AudioConfig, AudioInfo, validate_uploaded_audio, chunk_long_audio
from .dataset import (
    SpeechManifestEntry,
    ValidationResult,
    load_manifest,
    validate_manifest,
    create_splits,
    generate_dataset_statistics,
    save_splits,
    save_validation_report,
    save_dataset_config,
)
from .model import WhisperModelConfig, WhisperModelManager, HuggingFaceWhisperProvider
from .training import WhisperFineTuneConfig, WhisperFineTuner, run_finetune, WhisperDataCollator
from .evaluation import (
    EvaluationConfig,
    SpeechEvaluator,
    EvaluationResult,
    SamplePrediction,
    compare_models,
    evaluate_model,
)
from .experiment import (
    SpeechExperimentConfig,
    SpeechModelInfo,
    SpeechModelRegistry,
    create_experiment_config,
    generate_experiment_report,
)
from .cli import main as cli_main

__all__ = [
    # Audio
    "AudioPreprocessor",
    "AudioConfig",
    "AudioInfo",
    "validate_uploaded_audio",
    "chunk_long_audio",
    # Dataset
    "SpeechManifestEntry",
    "ValidationResult",
    "load_manifest",
    "validate_manifest",
    "create_splits",
    "generate_dataset_statistics",
    "save_splits",
    "save_validation_report",
    "save_dataset_config",
    # Model
    "WhisperModelConfig",
    "WhisperModelManager",
    "HuggingFaceWhisperProvider",
    # Training
    "WhisperFineTuneConfig",
    "WhisperFineTuner",
    "run_finetune",
    "WhisperDataCollator",
    # Evaluation
    "EvaluationConfig",
    "SpeechEvaluator",
    "EvaluationResult",
    "SamplePrediction",
    "compare_models",
    "evaluate_model",
    # Experiment
    "SpeechExperimentConfig",
    "SpeechModelInfo",
    "SpeechModelRegistry",
    "create_experiment_config",
    "generate_experiment_report",
    # CLI
    "cli_main",
]