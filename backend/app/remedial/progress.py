"""Observed practice progress.

Progress is a plain record of practice activity (sessions, activities,
recent performance) — deliberately kept as "observed practice activity".
It is never presented as a clinical improvement, a forecast, or evidence
about a child's condition.

Safety: invalid or incomplete telemetry is skipped (never used to shift a
trend).  A single practice session never produces a comparison.
"""

from ..models import PracticeSession
from .catalog import get_activity, ACTIVITIES
from .config import REMEDIAL_CONFIG

NOTE = (
    "Practice progress reflects observed practice activity only. "
    "It is not a diagnosis, forecast, or clinical claim."
)

_ALL_ACTIVE = tuple(a for a in ACTIVITIES if a.enabled)


def _responses(session: PracticeSession) -> list[dict]:
    """Extract well-formed response records; drop anything malformed."""
    responses = []
    for event in session.events:
        if event.event_type != "RESPONSE_SUBMITTED":
            continue
        payload = event.payload or {}
        if not isinstance(payload.get("correct"), bool):
            continue
        responses.append(
            {
                "correct": payload["correct"],
                "difficulty": payload.get("difficulty"),
            }
        )
    return responses


def _activity_name(activity_id: str) -> str:
    activity = get_activity(activity_id)
    return activity.display_name if activity else activity_id


def build_practice_progress(db, child_id) -> dict:
    history = (
        db.query(PracticeSession)
        .filter(PracticeSession.child_id == child_id)
        .order_by(PracticeSession.completed_at.asc().nullsfirst())
        .all()
    )

    attempted = list(history)
    completed = [s for s in history if s.status == "completed" and s.completed_at is not None]

    completed_ids: set[str] = set()
    by_activity: dict[str, dict] = {}
    for session in completed:
        completed_ids.add(session.activity_id)

    for activity_id in sorted({s.activity_id for s in history}):
        sessions_for = [s for s in history if s.activity_id == activity_id]
        completed_for = [s for s in completed if s.activity_id == activity_id]
        record: dict = {
            "activity_id": activity_id,
            "activity_name": _activity_name(activity_id),
            "target_domain": sessions_for[0].target_domain,
            "attempts": len(sessions_for),
            "completed": len(completed_for),
        }
        if completed_for:
            last_completed = max(s.completed_at for s in completed_for)
            record["last_completed_at"] = last_completed.isoformat()

        # Observed performance only from completed sessions with responses.
        sessions_with_responses = [s for s in completed_for if _responses(s)]
        if sessions_with_responses:
            accuracies = [
                sum(r["correct"] for r in _responses(s)) / len(_responses(s))
                for s in sessions_with_responses
            ]
            record["accuracy_observed"] = round(sum(accuracies) / len(accuracies), 3)

        # First vs latest comparison: only when at least two completed
        # sessions carry valid responses.
        if len(sessions_with_responses) >= 2:
            ordered = sorted(
                sessions_with_responses,
                key=lambda s: s.completed_at or s.started_at or s.created_at,
            )
            first = _responses(ordered[0])
            latest = _responses(ordered[-1])
            if first and latest:
                record["first_accuracy_observed"] = round(
                    sum(r["correct"] for r in first) / len(first), 3
                )
                record["latest_accuracy_observed"] = round(
                    sum(r["correct"] for r in latest) / len(latest), 3
                )

        by_activity[activity_id] = record

    recent_list = sorted(
        [s for s in completed if s.completed_at is not None],
        key=lambda s: s.completed_at,
        reverse=True,
    )[:_RECENT_LIMIT]

    return {
        "child_id": str(child_id),
        "totals": {
            "sessions_attempted": len(attempted),
            "sessions_completed": len(completed),
            "activities_completed": len(completed_ids),
            "activities_available": len(_ALL_ACTIVE),
        },
        "by_activity": sorted(by_activity.values(), key=lambda r: r["activity_id"]),
        "recent_completed": [
            {
                "id": str(s.id),
                "activity_id": s.activity_id,
                "activity_name": _activity_name(s.activity_id),
                "difficulty": s.difficulty,
                "completed_at": s.completed_at.isoformat(),
            }
            for s in recent_list
        ],
        "note": NOTE,
    }


_RECENT_LIMIT = REMEDIAL_CONFIG.recent_practice_limit