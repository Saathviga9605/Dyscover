"""Synthetic interaction-profile research pipeline for Dyscover.

This package generates simulator-defined behavior profiles under documented assumptions.
Its labels describe software interaction patterns, not dyslexia diagnoses.
Its models are strictly separated from production inference and clinical assessment.
"""

from __future__ import annotations

from .games import (
    SPEECH_GAMES,
    SUPPORTED_GAMES,
    SUPPORTED_LANGUAGES,
    VISUAL_GAMES,
    validate_game_language_pair,
)
from .generator import (
    CONTENT_VERSION,
    SIMULATOR_VERSION,
    SYNTHETIC_SCHEMA_VERSION,
    SyntheticConfig,
    ensure_synthetic_purity,
    export_dataset,
    generate_dataset,
)
from .inference import infer_synthetic_profile
from .pipeline import (
    get_synthetic_estimator,
    load_synthetic_model,
    train_synthetic_models,
)
from .quality import (
    generate_negative_fixtures,
    validate_synthetic_row,
)
from .registry import (
    RESEARCH_REGISTRY,
    ResearchArtifactRegistry,
    SyntheticModelRecord,
)
from .taxonomy import (
    ELIGIBLE_SCENARIOS,
    PROFILES,
    SCENARIO_DEFINITIONS,
    SUPPORTED_SCENARIOS,
    ScenarioProfile,
)

__all__ = [
    "CONTENT_VERSION",
    "ELIGIBLE_SCENARIOS",
    "PROFILES",
    "RESEARCH_REGISTRY",
    "ResearchArtifactRegistry",
    "SCENARIO_DEFINITIONS",
    "SIMULATOR_VERSION",
    "SPEECH_GAMES",
    "SUPPORTED_GAMES",
    "SUPPORTED_LANGUAGES",
    "SUPPORTED_SCENARIOS",
    "SYNTHETIC_SCHEMA_VERSION",
    "ScenarioProfile",
    "SyntheticConfig",
    "SyntheticModelRecord",
    "VISUAL_GAMES",
    "ensure_synthetic_purity",
    "export_dataset",
    "generate_dataset",
    "generate_negative_fixtures",
    "get_synthetic_estimator",
    "infer_synthetic_profile",
    "load_synthetic_model",
    "train_synthetic_models",
    "validate_game_language_pair",
    "validate_synthetic_row",
]

