"""Server-side trial scoring.

For games whose evaluation is a pure function of the stimulus and the response,
the server recomputes ``correctness`` and ``score`` instead of trusting the
client. These functions mirror ``frontend/src/games/definitions/*.ts``
``evaluateResponse``; ``tests/test_assessment_scoring.py`` pins the parity.

Limitation: stimuli are generated in the browser, so the server verifies that a
result is consistent with the submitted stimulus — it cannot prove the stimulus
itself was shown. Speech games grade a browser transcript; their correctness is
recorded as ``client_reported``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

VISUAL_GAMES = ("letter-detective", "mirror-match", "word-flash", "sequence-quest", "word-maze")
SPEECH_GAMES = ("sound-quest-adventure", "letter-bubble-pop", "maze-runner-rush")
KNOWN_GAMES = frozenset(VISUAL_GAMES + SPEECH_GAMES)

SCORING_SERVER = "server_verified"
SCORING_CLIENT = "client_reported"


class InvalidTrial(ValueError):
    """The submitted trial is internally inconsistent and cannot be scored."""


@dataclass(frozen=True)
class Scored:
    correct: bool
    score: float


def _letter_detective(stimulus: Any, expected: Any, actual: Any) -> Scored:
    if not isinstance(expected, str):
        raise InvalidTrial("expected_response must be a string")
    correct = actual is not None and str(actual).lower() == expected
    return Scored(correct, 1.0 if correct else 0.0)


def _word_flash(stimulus: Any, expected: Any, actual: Any) -> Scored:
    if not isinstance(expected, str):
        raise InvalidTrial("expected_response must be a string")
    correct = actual == expected
    return Scored(correct, 1.0 if correct else 0.0)


def _mirror_match(stimulus: Any, expected: Any, actual: Any) -> Scored:
    if not isinstance(stimulus, dict) or not isinstance(stimulus.get("options"), list):
        raise InvalidTrial("stimulus.options is required")
    target = stimulus.get("targetOrientation")
    options = [option for option in stimulus["options"] if isinstance(option, dict)]
    chosen = next((option for option in options if option.get("id") == actual), None)
    correct = chosen is not None and chosen.get("orientation") == target
    return Scored(correct, 1.0 if correct else 0.0)


def _sequence_quest(stimulus: Any, expected: Any, actual: Any) -> Scored:
    if not isinstance(expected, list) or not expected:
        raise InvalidTrial("expected_response must be a non-empty list")
    submitted = actual if isinstance(actual, list) else []
    positions = sum(1 for index, item in enumerate(submitted[: len(expected)]) if item == expected[index])
    return Scored(positions == len(expected), positions / len(expected))


def _word_maze(stimulus: Any, expected: Any, actual: Any) -> Scored:
    if not isinstance(expected, list) or not expected:
        raise InvalidTrial("expected_response must be a non-empty list")
    submitted = actual if isinstance(actual, list) else []
    # Only distinct words that are actually hidden in the maze count as found.
    found = {word for word in submitted if word in expected}
    return Scored(len(found) == len(set(expected)), len(found) / len(set(expected)))


_SCORERS: dict[str, Callable[[Any, Any, Any], Scored]] = {
    "letter-detective": _letter_detective,
    "word-flash": _word_flash,
    "mirror-match": _mirror_match,
    "sequence-quest": _sequence_quest,
    "word-maze": _word_maze,
}


def score_trial(game_id: str, stimulus: Any, expected: Any, actual: Any) -> Scored | None:
    """Return the server-computed result, or None when the game is client-scored."""
    scorer = _SCORERS.get(game_id)
    return scorer(stimulus, expected, actual) if scorer else None
