from collections import Counter
from datetime import datetime
from typing import Any


def validate_trials(trials: list[Any], events: list[Any]) -> dict[str, Any]:
    issues: list[str] = []
    trial_ids = [str(trial.id) for trial in trials]
    duplicate_trials = len(trial_ids) - len(set(trial_ids))
    if duplicate_trials:
        issues.append("duplicate_trial_ids")
    for trial in trials:
        if trial.reaction_time_ms is not None and trial.reaction_time_ms < 0:
            issues.append(f"negative_reaction_time:{trial.id}")
        if trial.score < 0:
            issues.append(f"negative_score:{trial.id}")
        if trial.started_at and trial.completed_at and trial.completed_at < trial.started_at:
            issues.append(f"completion_before_start:{trial.id}")
    event_keys = [(str(event.trial_id), event.sequence_number) for event in events]
    duplicate_events = len(event_keys) - len(set(event_keys))
    if duplicate_events:
        issues.append("duplicate_event_sequence")
    return {"valid": not issues, "issues": issues, "duplicate_events": max(0, duplicate_events), "incomplete_trials": sum(trial.completed_at is None for trial in trials)}


def build_quality_report(sessions: list[Any], all_trials: list[Any], gaze_trial_ids: set[str] | None = None) -> dict[str, Any]:
    gaze_trial_ids = gaze_trial_ids or set()
    valid_sessions = sum(bool(getattr(session, "completed_at", None)) for session in sessions)
    zero_trial_sessions = sum(not getattr(session, "games", None) for session in sessions)
    warnings = []
    if zero_trial_sessions: warnings.append("One or more sessions contain no trials.")
    if not all_trials: warnings.append("No trials are available for feature extraction.")
    invalid_sessions = len(sessions) - valid_sessions
    return {"status": "invalid" if invalid_sessions else ("warning" if warnings else "ok"), "schema_version": "1.0", "total_sessions": len(sessions), "total_trials": len(all_trials), "valid_sessions": valid_sessions, "invalid_sessions": invalid_sessions, "missing_feature_percentage": {}, "missing_feature_rates": {}, "invalid_feature_counts": {}, "gaze_availability": (len(gaze_trial_ids) / len(all_trials) if all_trials else 0), "speech_availability": 0.0, "incomplete_trials": sum(trial.completed_at is None for trial in all_trials), "duplicate_events": 0, "outlier_counts": {}, "zero_trial_sessions": zero_trial_sessions, "warnings": warnings}
