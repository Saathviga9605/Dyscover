"""Deterministic, bounded adaptive difficulty.

Adapts a game's difficulty level (1..5) from a recent window of completed
trials, using hysteresis:

- Level is only changed to a neighbouring value (±1) — never more.
- Change requires a recent-window accuracy clearly above or below the
  configured thresholds, and at least ``min_window_samples`` recent trials.
- Insufficient evidence => the configured default level is returned.
- Extra caution (no change) whenever the window sits between thresholds.
"""

from dataclasses import dataclass

from . import evidence
from .config import DifficultyRules


@dataclass
class DifficultyDecision:
    level: int
    previous_level: int | None
    default: int
    window_size: int
    reason: str
    changed: bool


def _recent_window(trials, window: int) -> list:
    completed = [t for t in trials if evidence.is_valid(t)]
    return completed[-window:]


def decide(game_id: str, trials: list, rules: DifficultyRules, current_level: int | None = None) -> DifficultyDecision:
    bounds = {"minimum": rules.minimum_level, "maximum": rules.maximum_level}
    default = rules.default_level
    if current_level is None:
        current_level = default
    current_level = max(bounds["minimum"], min(bounds["maximum"], current_level))

    window = _recent_window(trials, rules.recent_window)
    if len(window) < rules.min_window_samples:
        reason = "Not enough recent completed observations to adjust difficulty."
        return _decision(default if current_level == default else current_level, current_level, default, len(window), reason, False)

    accuracy = sum(1 for t in window if t.correctness) / len(window)
    latest = current_level
    changed = False
    reason = "Recent observations were within expected range; difficulty held."

    if accuracy >= rules.increase_accuracy:
        candidate = min(bounds["maximum"], current_level + rules.step)
        if candidate != current_level:
            latest, changed = candidate, True
            reason = "Recent observations show a comfortable pattern; a slightly higher level may be appropriate."
    elif accuracy <= rules.decrease_accuracy:
        candidate = max(bounds["minimum"], current_level - rules.step)
        if candidate != current_level:
            latest, changed = candidate, True
            reason = "Recent observations suggest adjusting to a slightly easier level for continued practice."
        else:
            reason = "At minimum level; difficulty held."

    return _decision(latest, current_level, default, len(window), reason, changed)


def _decision(level, previous, default, window_size, reason, changed) -> DifficultyDecision:
    return DifficultyDecision(
        level=level,
        previous_level=previous,
        default=default,
        window_size=window_size,
        reason=reason,
        changed=changed,
    )