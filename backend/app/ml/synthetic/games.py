"""Game definitions, domain mappings, and language constraints for the synthetic simulator.

These specifications accurately mirror the games, difficulty tiers, stimuli, and
language-availability matrices implemented in Dyscover Stage 7.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

VISUAL_GAMES = (
    "letter-detective",
    "mirror-match",
    "word-flash",
    "sequence-quest",
    "word-maze",
)

SPEECH_GAMES = (
    "sound-quest-adventure",
    "letter-bubble-pop",
    "maze-runner-rush",
)

SUPPORTED_GAMES: tuple[str, ...] = (*VISUAL_GAMES, *SPEECH_GAMES)

# Canonical languages supported in the application
SUPPORTED_LANGUAGES = frozenset({"en", "ta"})
DEFAULT_LANGUAGE = "en"

# Honest language availability: mirror-match is shape/orientation discrimination and
# therefore language-neutral. All other visual and speech games are curated in English only.
LANGUAGE_AVAILABILITY: dict[str, frozenset[str]] = {
    "letter-detective": frozenset({"en"}),
    "mirror-match": frozenset({"en", "ta"}),
    "word-flash": frozenset({"en"}),
    "sequence-quest": frozenset({"en"}),
    "word-maze": frozenset({"en"}),
    "sound-quest-adventure": frozenset({"en"}),
    "letter-bubble-pop": frozenset({"en"}),
    "maze-runner-rush": frozenset({"en"}),
}

GAME_DOMAINS: dict[str, str] = {
    "letter-detective": "visual-symbol-discrimination",
    "mirror-match": "visual-symbol-discrimination",
    "word-flash": "orthographic-recognition",
    "sequence-quest": "working-memory",
    "word-maze": "attention-visual-search",
    "sound-quest-adventure": "phonological-awareness",
    "letter-bubble-pop": "phonological-awareness",
    "maze-runner-rush": "rapid-naming",
}

# Supported difficulty levels per game
GAME_DIFFICULTY_LEVELS: dict[str, tuple[int, ...]] = {
    "letter-detective": (1, 2, 3, 4, 5),
    "mirror-match": (1, 2, 3, 4, 5),
    "word-flash": (1, 2, 3, 4, 5),
    "sequence-quest": (1, 2, 3, 4, 5),
    "word-maze": (1, 2, 3, 4, 5),
    "sound-quest-adventure": (1, 2, 3),
    "letter-bubble-pop": (1, 2, 3),
    "maze-runner-rush": (1, 2, 3),
}

# Stimulus pools from the actual game implementations
STIMULI_CATALOG: dict[str, dict[str, Any]] = {
    "letter-detective": {
        "pools_by_difficulty": {
            1: ("a", "m", "s", "t"),
            2: ("b", "d", "p", "q"),
            3: ("m", "n", "u", "w"),
            4: ("b", "d", "p", "q", "g", "f"),
            5: ("b", "d", "p", "q", "m", "n", "u", "w"),
        }
    },
    "mirror-match": {
        "symbols": ("b", "d", "p", "q", "m", "w"),
        "orientations": ("normal", "mirror", "rotated"),
    },
    "word-flash": {
        "pools_by_difficulty": {
            1: ("cat", "sun", "dog", "map"),
            2: ("book", "fish", "tree", "moon"),
            3: ("plant", "chair", "train", "small"),
            4: ("bright", "friend", "street", "cloud"),
            5: ("because", "between", "together", "another"),
        }
    },
    "sequence-quest": {
        "items": ("star", "moon", "sun", "leaf", "cloud", "wave"),
        "lengths_by_difficulty": {1: 3, 2: 4, 3: 5, 4: 6, 5: 6},
    },
    "word-maze": {
        "pools_by_difficulty": {
            1: ("cat", "sun", "dog", "map", "hat", "bed"),
            2: ("dog", "map", "fish", "moon", "star", "tree", "bird", "frog"),
            3: ("moon", "star", "tree", "bird", "fish", "rain", "boat", "cake"),
            4: ("plant", "cloud", "train", "beach", "rocket", "pencil", "castle"),
            5: ("bright", "friend", "garden", "stream", "flower", "castle", "island"),
        }
    },
    "sound-quest-adventure": {
        "levels": {
            1: {"kind": "word", "pool": ("cat", "dog", "pin", "bat", "mat", "sit", "top", "run", "bed", "pig")},
            2: {"kind": "word", "pool": ("rabbit", "sunny", "paper", "tiger", "pat bat", "sip ship")},
            3: {"kind": "sentence", "pool": ("The red fox ran home.", "A little puppy found a bone.", "Mina opens the magic gate.")},
        }
    },
    "letter-bubble-pop": {
        "levels": {
            1: {"kind": "letter", "pool": ("b", "d", "p", "q", "m", "w")},
            2: {"kind": "letter-pair", "pool": ("ba", "da", "pa", "ma")},
            3: {"kind": "word", "pool": ("bat", "dad", "pan", "mat")},
        }
    },
    "maze-runner-rush": {
        "levels": {
            1: {"kind": "ran", "pool": ("red", "blue", "green", "yellow")},
            2: {"kind": "word", "pool": ("jump", "run", "stop", "go")},
            3: {"kind": "word", "pool": ("fast", "slow", "high", "low")},
        }
    },
}


def validate_game_language_pair(game_id: str, language: str) -> None:
    """Validate that game supports the requested language according to honest content availability."""
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Language '{language}' is not supported. Supported: {sorted(SUPPORTED_LANGUAGES)}")
    if game_id not in SUPPORTED_GAMES:
        raise ValueError(f"Game '{game_id}' is not supported. Supported: {sorted(SUPPORTED_GAMES)}")
    allowed = LANGUAGE_AVAILABILITY.get(game_id, frozenset({"en"}))
    if language not in allowed:
        raise ValueError(
            f"Game '{game_id}' does not have curated content for language '{language}'. "
            f"Supported languages for '{game_id}': {sorted(allowed)}. "
            f"Tamil ('ta') is only supported for language-neutral 'mirror-match'."
        )

