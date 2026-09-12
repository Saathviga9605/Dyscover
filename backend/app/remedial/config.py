"""Remedial engine configuration.

Small, explicit, versioned knobs.  These are product/content rules, not
clinical thresholds.  Selection remains deterministic for a given
(profile, history, age, config).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RemedialConfig:
    engine_version: str = "1.0.0"
    content_version: str = "1.0"
    difficulty_minimum: int = 1
    difficulty_maximum: int = 5
    default_difficulty: int = 1
    # Hours after a completed practice session before the same activity is
    # recommended again, so practice is spaced rather than repetitive.
    activity_cooldown_hours: int = 24
    # Focus categories in priority order (highest first).
    focus_priority: tuple[str, ...] = ("practice_opportunity", "developing")
    default_age_min: int = 4
    default_age_max: int = 10
    recent_practice_limit: int = 5
    max_per_activity_ties: int = 1


REMEDIAL_CONFIG = RemedialConfig()