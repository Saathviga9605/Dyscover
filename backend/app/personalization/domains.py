"""Canonical domain/skill model and game-to-domain mapping.

Only domains already supported by the Dyscover assessment architecture are
used (see ``app.assessment.AssessmentDomain``).  No new domains are invented
in Stage 5.
"""

from app.assessment import AssessmentDomain

DOMAIN_LABELS: dict[str, str] = {
    AssessmentDomain.VISUAL_SYMBOL_DISCRIMINATION.value: "Visual symbol discrimination",
    AssessmentDomain.ORTHOGRAPHIC_RECOGNITION.value: "Orthographic recognition",
    AssessmentDomain.PHONOLOGICAL_AWARENESS.value: "Phonological awareness",
    AssessmentDomain.WORKING_MEMORY.value: "Working memory",
    AssessmentDomain.SEQUENCING.value: "Sequencing",
    AssessmentDomain.ATTENTION_VISUAL_SEARCH.value: "Attention / visual search",
    AssessmentDomain.READING_FLUENCY.value: "Reading fluency",
    AssessmentDomain.INTERACTION_BEHAVIOR.value: "Interaction behavior",
}

# Canonical game id -> observed domain mapping (mirrors the five games).
GAME_DOMAIN: dict[str, str] = {
    "letter-detective": AssessmentDomain.VISUAL_SYMBOL_DISCRIMINATION.value,
    "mirror-match": AssessmentDomain.VISUAL_SYMBOL_DISCRIMINATION.value,
    "word-flash": AssessmentDomain.ORTHOGRAPHIC_RECOGNITION.value,
    "sequence-quest": AssessmentDomain.WORKING_MEMORY.value,
    "word-maze": AssessmentDomain.ATTENTION_VISUAL_SEARCH.value,
}

GAMES_BY_DOMAIN: dict[str, list[str]] = {}
for _game_id, _domain in GAME_DOMAIN.items():
    GAMES_BY_DOMAIN.setdefault(_domain, []).append(_game_id)

# Default game order used for recommendations (matches the child flow).
DEFAULT_GAME_ORDER: tuple[str, ...] = (
    "letter-detective",
    "mirror-match",
    "word-flash",
    "sequence-quest",
    "word-maze",
)

# Difficulty support is uniform (1..5) across all five games today.
DIFFICULTY_BY_GAME: dict[str, dict[str, int]] = {
    game_id: {"minimum": 1, "maximum": 5} for game_id in DEFAULT_GAME_ORDER
}

SUPPORTED_DOMAINS: tuple[str, ...] = tuple(
    domain
    for domain in (
        AssessmentDomain.VISUAL_SYMBOL_DISCRIMINATION.value,
        AssessmentDomain.ORTHOGRAPHIC_RECOGNITION.value,
        AssessmentDomain.WORKING_MEMORY.value,
        AssessmentDomain.ATTENTION_VISUAL_SEARCH.value,
    )
    if domain in GAMES_BY_DOMAIN
)

DOMAIN_ORDER: tuple[str, ...] = SUPPORTED_DOMAINS


def domain_label(domain: str) -> str:
    return DOMAIN_LABELS.get(domain, domain)


def game_domain(game_id: str) -> str | None:
    return GAME_DOMAIN.get(game_id)


def games_for_domain(domain: str) -> list[str]:
    return GAMES_BY_DOMAIN.get(domain, [])


def ordered_games(domain: str) -> list[str]:
    games = games_for_domain(domain)
    return [game for game in DEFAULT_GAME_ORDER if game in games]