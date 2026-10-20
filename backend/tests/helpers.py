"""Builders for internally consistent trial payloads.

The API recomputes correctness for visual games (``app.assessments.scoring``),
so tests that need a particular outcome must submit a response that produces it.
"""

from __future__ import annotations

from typing import Any

MIRROR_OPTIONS = [
    {"id": "option-0", "label": "b", "orientation": "normal"},
    {"id": "option-1", "label": "b", "orientation": "mirrored"},
]


def outcome(game_id: str, correct: bool | None) -> dict[str, Any]:
    """Stimulus/expected/actual/correctness fields that score as ``correct``.

    ``correct=None`` produces an unanswered, unscored trial.
    """
    if game_id == "letter-detective":
        base = {"stimulus": {"target": "b", "options": ["b", "d"]}, "expected_response": "b"}
        actual = "b" if correct else "d"
    elif game_id == "word-flash":
        base = {"stimulus": {"word": "cat", "options": ["cat", "bat"]}, "expected_response": "cat"}
        actual = "cat" if correct else "bat"
    elif game_id == "mirror-match":
        base = {"stimulus": {"symbol": "b", "targetOrientation": "normal", "options": MIRROR_OPTIONS}, "expected_response": "option-0"}
        actual = "option-0" if correct else "option-1"
    elif game_id == "sequence-quest":
        base = {"stimulus": {"sequence": ["sun", "moon", "star"], "displayMs": 2500}, "expected_response": ["sun", "moon", "star"]}
        actual = ["sun", "moon", "star"] if correct else ["star", "moon", "sun"]
    elif game_id == "word-maze":
        base = {"stimulus": {"grid": [["c", "a", "t"]], "targets": ["cat", "dog"]}, "expected_response": ["cat", "dog"]}
        actual = ["cat", "dog"] if correct else ["cat"]
    else:  # speech games are client-scored
        base = {"stimulus": {"promptText": "cat", "kind": "word", "level": 1}, "expected_response": "cat"}
        actual = "cat" if correct else "bat"
    if correct is None:
        return {**base, "actual_response": None, "correctness": None}
    return {**base, "actual_response": actual, "correctness": correct}


def trial_payload(game_id: str, trial_number: int, correct: bool | None, **overrides: Any) -> dict[str, Any]:
    payload = {
        "trial_number": trial_number,
        "game_version": "1.0.0",
        "difficulty": 2,
        "completed_at": "2026-01-01T12:00:05.000Z",
        **outcome(game_id, correct),
    }
    payload.update(overrides)
    return payload
