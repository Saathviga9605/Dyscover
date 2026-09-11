"""Progress and trend computation across assessments.

Produces a time-ordered, per-assessment summary of observed domain accuracy
for a child, plus a comparison of the most recent and earliest observations
where enough data exists.  Trend direction is a plain arithmetic comparison
of deterministic domain accuracies — never a projection or forecast.
"""

from .config import PersonalizationConfig
from .domains import GAME_DOMAIN
from .skills import _accuracy


def _assessment_points(assessments_and_trials, config: PersonalizationConfig) -> list[dict]:
    """assessments_and_trials: iterable of (assessment, trials)."""
    points = []
    for assessment, trials in assessments_and_trials:
        by_domain: dict[str, list] = {}
        for trial in trials:
            domain = GAME_DOMAIN.get(trial.game_id)
            if domain is None:
                continue
            by_domain.setdefault(domain, []).append(trial)
        accuracy_by_domain = {
            domain: _accuracy(trials_for_domain)
            for domain, trials_for_domain in by_domain.items()
            if _accuracy(trials_for_domain) is not None
        }
        points.append(
            {
                "assessment_id": str(assessment.id),
                "completed_at": assessment.completed_at.isoformat() if assessment.completed_at else None,
                "domains": {
                    domain: round(value, 4) for domain, value in sorted(accuracy_by_domain.items())
                },
            }
        )
    return points


def build_progress(assessments_and_trials, config: PersonalizationConfig) -> dict:
    points = _assessment_points(assessments_and_trials, config)

    # Deterministic comparison of earliest vs most recent completed point.
    comparison = None
    if len(points) >= 2:
        first, last = points[0], points[-1]
        compared_domains = sorted(set(first["domains"]) & set(last["domains"]))
        if compared_domains:
            comparison = {
                "earliest_assessment_id": first["assessment_id"],
                "latest_assessment_id": last["assessment_id"],
                "domains": {
                    domain: {
                        "earliest_accuracy": first["domains"][domain],
                        "latest_accuracy": last["domains"][domain],
                        "delta": round(last["domains"][domain] - first["domains"][domain], 4),
                    }
                    for domain in compared_domains
                },
            }

    return {
        "points": points,
        "comparison": comparison,
        "note": "Progress is computed from observed, completed activity only and is not a forecast.",
    }