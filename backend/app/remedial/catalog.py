"""Remedial activity catalog.

Canonical activity definitions.  An activity is a versioned, curated practice
opportunity targetting one Stage 5 learning domain.  Each activity reuses an
existing game (the "supporting game") as its practice shell; the engine does
not redesign assessment games.

New activities are added to this catalog without changing the selection,
session, or telemetry code.
"""

from dataclasses import dataclass

from .config import REMEDIAL_CONFIG

SUPPORTING_GAMES = {
    "symbol-match": "letter-detective",
    "word-builder": "word-flash",
    "sequence-recall": "sequence-quest",
    "visual-search": "word-maze",
}

_DIFFICULTY_LEVELS = tuple(range(REMEDIAL_CONFIG.difficulty_minimum, REMEDIAL_CONFIG.difficulty_maximum + 1))


@dataclass(frozen=True)
class ActivityDefinition:
    activity_id: str
    display_name: str
    description: str
    target_domain: str
    supporting_game: str
    supported_difficulty_levels: tuple[int, ...]
    age_min: int
    age_max: int
    estimated_duration_minutes: int
    activity_type: str
    required_capabilities: tuple[str, ...]
    version: str
    enabled: bool

    def to_dict(self) -> dict:
        return {
            "activity_id": self.activity_id,
            "display_name": self.display_name,
            "description": self.description,
            "target_domain": self.target_domain,
            "supporting_game": self.supporting_game,
            "supported_difficulty_levels": list(self.supported_difficulty_levels),
            "age_range": [self.age_min, self.age_max],
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "activity_type": self.activity_type,
            "required_capabilities": list(self.required_capabilities),
            "version": self.version,
            "enabled": self.enabled,
        }


# Age appropriateness (4-10) is a product/content constraint from the Stage 2
# product brief, not a clinical norm. All four Stage 6 activities share it.
ACTIVITIES: tuple[ActivityDefinition, ...] = (
    ActivityDefinition(
        activity_id="symbol-match",
        display_name="Symbol Match",
        description="Match a symbol to its twin from a small group of similar symbols.",
        target_domain="visual-symbol-discrimination",
        supporting_game=SUPPORTING_GAMES["symbol-match"],
        supported_difficulty_levels=_DIFFICULTY_LEVELS,
        age_min=REMEDIAL_CONFIG.default_age_min,
        age_max=REMEDIAL_CONFIG.default_age_max,
        estimated_duration_minutes=5,
        activity_type="practice",
        required_capabilities=("pointer",),
        version="1.0.0",
        enabled=True,
    ),
    ActivityDefinition(
        activity_id="word-builder",
        display_name="Word Builder",
        description="Build a word by choosing its letters or matching a word to a short version.",
        target_domain="orthographic-recognition",
        supporting_game=SUPPORTING_GAMES["word-builder"],
        supported_difficulty_levels=_DIFFICULTY_LEVELS,
        age_min=REMEDIAL_CONFIG.default_age_min,
        age_max=REMEDIAL_CONFIG.default_age_max,
        estimated_duration_minutes=5,
        activity_type="practice",
        required_capabilities=("pointer",),
        version="1.0.0",
        enabled=True,
    ),
    ActivityDefinition(
        activity_id="sequence-recall",
        display_name="Sequence Recall",
        description="Watch a short sequence of pictures and repeat the same order.",
        target_domain="working-memory",
        supporting_game=SUPPORTING_GAMES["sequence-recall"],
        supported_difficulty_levels=_DIFFICULTY_LEVELS,
        age_min=REMEDIAL_CONFIG.default_age_min,
        age_max=REMEDIAL_CONFIG.default_age_max,
        estimated_duration_minutes=5,
        activity_type="practice",
        required_capabilities=("pointer",),
        version="1.0.0",
        enabled=True,
    ),
    ActivityDefinition(
        activity_id="visual-search",
        display_name="Visual Search",
        description="Find a target picture among a busy group of lookalikes.",
        target_domain="attention-visual-search",
        supporting_game=SUPPORTING_GAMES["visual-search"],
        supported_difficulty_levels=_DIFFICULTY_LEVELS,
        age_min=REMEDIAL_CONFIG.default_age_min,
        age_max=REMEDIAL_CONFIG.default_age_max,
        estimated_duration_minutes=5,
        activity_type="practice",
        required_capabilities=("pointer",),
        version="1.0.0",
        enabled=True,
    ),
    ActivityDefinition(
        activity_id="sound-quest",
        display_name="Sound Quest",
        description="Read familiar short words aloud into the microphone.",
        target_domain="phonological-awareness",
        supporting_game=SUPPORTING_GAMES["word-builder"],
        supported_difficulty_levels=_DIFFICULTY_LEVELS,
        age_min=REMEDIAL_CONFIG.default_age_min,
        age_max=REMEDIAL_CONFIG.default_age_max,
        estimated_duration_minutes=5,
        activity_type="speech",
        required_capabilities=("microphone",),
        version="1.0.0",
        enabled=True,
    ),
    ActivityDefinition(
        activity_id="letter-pop",
        display_name="Letter Bubble Pop",
        description="Say the name of a letter as it pops up.",
        target_domain="reading-fluency",
        supporting_game=SUPPORTING_GAMES["symbol-match"],
        supported_difficulty_levels=_DIFFICULTY_LEVELS,
        age_min=REMEDIAL_CONFIG.default_age_min,
        age_max=REMEDIAL_CONFIG.default_age_max,
        estimated_duration_minutes=5,
        activity_type="speech",
        required_capabilities=("microphone",),
        version="1.0.0",
        enabled=True,
    ),
    ActivityDefinition(
        activity_id="maze-ran",
        display_name="Maze Runner (Say It)",
        description="Say each word in quick succession as it shows up.",
        target_domain="attention-visual-search",
        supporting_game=SUPPORTING_GAMES["visual-search"],
        supported_difficulty_levels=_DIFFICULTY_LEVELS,
        age_min=REMEDIAL_CONFIG.default_age_min,
        age_max=REMEDIAL_CONFIG.default_age_max,
        estimated_duration_minutes=5,
        activity_type="speech",
        required_capabilities=("microphone",),
        version="1.0.0",
        enabled=True,
    ),
)


def get_activity(activity_id: str) -> ActivityDefinition | None:
    return _by_id.get(activity_id)


def available_activities(age: int | None = None, capabilities: tuple[str, ...] | None = None) -> tuple[ActivityDefinition, ...]:
    """Enabled activities appropriate for *age* and *capabilities*, when known."""
    result = [a for a in ACTIVITIES if a.enabled]
    if capabilities is not None:
        result = [a for a in result if set(a.required_capabilities).issubset(set(capabilities))]
    if age is not None:
        result = [a for a in result if a.age_min <= age <= a.age_max]
    return tuple(result)


_by_id: dict[str, ActivityDefinition] = {a.activity_id: a for a in ACTIVITIES}