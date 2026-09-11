"""Centralized, documented personalization configuration.

Every constant here is an engineering / product-threshold decision — NOT a
clinical or validated threshold.  Changing any value changes the engine
version.  ``config_summary()`` makes the active configuration fully visible
in audit results.
"""

from dataclasses import dataclass, asdict
from . import PERSONALIZATION_ENGINE_VERSION


@dataclass(frozen=True)
class EvidenceThresholds:
    """Minimum-evidence rules for declaring a domain as having *sufficient_data*.

    These thresholds are product/engineering decisions about how many
    completed, valid trials are needed before a deterministic category
    is produced.  They are NOT clinical sensitivity/specificity values.
    """

    minimum_valid_trials: int = 3
    minimum_completed_trials: int = 2
    maximum_error_ratio: float = 0.50
    minimum_accuracy_samples: int = 3


@dataclass(frozen=True)
class CategoryThresholds:
    """Deterministic performance-category boundaries.

    These are observed-performance thresholds used only to describe
    what was seen in the current assessment, not to imply risk,
    diagnosis, or clinical impairment.
    """

    strength_accuracy: float = 0.80
    practice_accuracy: float = 0.50


@dataclass(frozen=True)
class DifficultyRules:
    """Adaptive difficulty hysteresis rules.

    Difficulty changes are modest (±1 level) and require clear
    evidence from a recent performance window.  No sudden jumps
    are allowed.  Insufficient data always defaults safely.
    """

    minimum_level: int = 1
    maximum_level: int = 5
    default_level: int = 1
    recent_window: int = 3
    increase_accuracy: float = 0.85
    decrease_accuracy: float = 0.40
    step: int = 1
    min_window_samples: int = 2


@dataclass(frozen=True)
class StimulusSpacingRules:
    """Stimulus-uniqueness safeguards.

    Prevents immediate repetition of the same stimulus where
    the game's ``createTrial`` produces a JSON-serialisable stimulus.
    """

    recent_window: int = 4
    maximum_retries: int = 6
    spacing_enabled: bool = True


@dataclass(frozen=True)
class PersonalizationConfig:
    """Single, frozen configuration object for the whole engine."""

    evidence: EvidenceThresholds = EvidenceThresholds()
    category: CategoryThresholds = CategoryThresholds()
    difficulty: DifficultyRules = DifficultyRules()
    stimulus: StimulusSpacingRules = StimulusSpacingRules()
    engine_version: str = PERSONALIZATION_ENGINE_VERSION


PERSONALIZATION_CONFIG = PersonalizationConfig()


def config_summary() -> dict:
    """Return the active configuration as an auditable dictionary."""
    return {
        "engine_version": PERSONALIZATION_ENGINE_VERSION,
        "config": asdict(PERSONALIZATION_CONFIG),
    }