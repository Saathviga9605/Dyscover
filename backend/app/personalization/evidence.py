"""Evidence sufficiency assessment.

Determines, for a collection of observed trials, whether there is enough
*valid* observation to categorize performance.  States are:

- ``no_data``: no trials were observed at all.
- ``insufficient_data``: some trials exist, but not enough valid/completed
  trials to produce a reliable deterministic category.
- ``sufficient_data``: enough valid trials to produce a category.

A trial is considered *valid* when it was completed with a recorded
correctness.  Timing outliers (negative reaction times) invalidate the trial
for timing aggregates only.
"""


class EvidenceState:
    NO_DATA = "no_data"
    INSUFFICIENT_DATA = "insufficient_data"
    SUFFICIENT_DATA = "sufficient_data"


def is_completed(trial) -> bool:
    return trial.completed_at is not None


def is_valid(trial) -> bool:
    return is_completed(trial) and trial.correctness is not None


def is_valid_timing(trial) -> bool:
    return is_valid(trial) and (trial.reaction_time_ms is None or trial.reaction_time_ms >= 0)


def classify(trials) -> str:
    if not trials:
        return EvidenceState.NO_DATA
    valid = sum(1 for trial in trials if is_valid(trial))
    completed = sum(1 for trial in trials if is_completed(trial))
    if valid <= 0:
        return EvidenceState.INSUFFICIENT_DATA
    error_ratio = 1.0 - (completed / len(trials)) if trials else 1.0
    return EvidenceState.SUFFICIENT_DATA


def report(trials, thresholds) -> dict:
    total = len(trials)
    valid = sum(1 for trial in trials if is_valid(trial))
    completed = sum(1 for trial in trials if is_completed(trial))
    state = EvidenceState.NO_DATA if total == 0 else (
        EvidenceState.SUFFICIENT_DATA
        if valid >= thresholds.minimum_valid_trials and completed >= thresholds.minimum_completed_trials
        else EvidenceState.INSUFFICIENT_DATA
    )
    return {
        "state": state,
        "trial_count": total,
        "valid_trial_count": valid,
        "completed_trial_count": completed,
        "incomplete_trial_count": total - completed,
        "minimum_valid_trials": thresholds.minimum_valid_trials,
    }