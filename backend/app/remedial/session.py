"""Practice-session lifecycle and practice telemetry.

Keeps practice data strictly separate from assessment evidence:

- ``PracticeSession`` lives in its own table with ``mode="practice"``.
- ``PracticeEvent`` reuses the canonical event vocabulary (event_type,
  timestamp, sequence_number, payload, schema_version) inside the practice
  collection, so practice activity is always identifiable as practice.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from ..models import PracticeEvent, PracticeSession
from . import REMEDIAL_EVENT_SCHEMA_VERSION, REMEDIAL_MODE
from .catalog import get_activity
from .config import REMEDIAL_CONFIG

STATUS_PLANNED = "planned"
STATUS_ACTIVE = "active"
STATUS_COMPLETED = "completed"
STATUS_ABANDONED = "abandoned"

VALID_STATES = {STATUS_PLANNED, STATUS_ACTIVE, STATUS_COMPLETED, STATUS_ABANDONED}

# Canonical event contract types available to practice telemetry.
ALLOWED_EVENT_TYPES = frozenset(
    {
        "SESSION_STARTED",
        "SESSION_PAUSED",
        "SESSION_RESUMED",
        "STIMULUS_SHOWN",
        "RESPONSE_SUBMITTED",
        "TRIAL_TIMEOUT",
        "HINT_SHOWN",
        "SESSION_COMPLETED",
        "SESSION_ABANDONED",
    }
)


class SessionError(Exception):
    """Raised when a practice-session state transition/event is invalid."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def clamp_level(level: int | None) -> int:
    if level is None:
        return REMEDIAL_CONFIG.default_difficulty
    return max(REMEDIAL_CONFIG.difficulty_minimum, min(REMEDIAL_CONFIG.difficulty_maximum, level))


def create_practice_session(db, child_id: uuid.UUID, activity_id: str, difficulty: int | None = None) -> PracticeSession:
    activity = get_activity(activity_id)
    if activity is None:
        raise SessionError(f"Unknown activity '{activity_id}'.", status_code=404)
    if not activity.enabled:
        raise SessionError(f"Activity '{activity_id}' is not available.", status_code=404)

    session = PracticeSession(
        id=uuid.uuid4(),
        child_id=child_id,
        mode=REMEDIAL_MODE,
        activity_id=activity.activity_id,
        target_domain=activity.target_domain,
        difficulty=clamp_level(difficulty),
        activity_version=activity.version,
        content_version=REMEDIAL_CONFIG.content_version,
        config_version=REMEDIAL_CONFIG.engine_version,
        status=STATUS_PLANNED,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db, session_id: uuid.UUID) -> PracticeSession | None:
    return db.get(PracticeSession, session_id)


def _require(db, session_id: uuid.UUID) -> PracticeSession:
    session = get_session(db, session_id)
    if session is None:
        raise SessionError(f"Unknown practice session '{session_id}'.", status_code=404)
    return session


def start_session(db, session_id: uuid.UUID) -> PracticeSession:
    session = _require(db, session_id)
    if session.status != STATUS_PLANNED:
        raise SessionError(
            f"Cannot start a session in state '{session.status}'.", status_code=409
        )
    session.status = STATUS_ACTIVE
    session.started_at = datetime.now(timezone.utc)
    record_event(db, session.id, "SESSION_STARTED", payload={"difficulty": session.difficulty, "activity_id": session.activity_id}, session=session)
    db.commit()
    db.refresh(session)
    return session


def record_event(
    db,
    session_id: uuid.UUID,
    event_type: str,
    payload: dict | None = None,
    *,
    timestamp: datetime | None = None,
    session: PracticeSession | None = None,
) -> PracticeEvent:
    if event_type not in ALLOWED_EVENT_TYPES:
        raise SessionError(f"Event type '{event_type}' is not part of the practice event contract.", status_code=400)
    if session is None:
        session = _require(db, session_id)
    if session.status not in {STATUS_ACTIVE, STATUS_PLANNED}:
        raise SessionError(
            f"Events cannot be recorded for a session in state '{session.status}'.", status_code=409
        )

    sequence = len(session.events)
    event = PracticeEvent(
        id=uuid.uuid4(),
        practice_session_id=session.id,
        mode=REMEDIAL_MODE,
        event_type=event_type,
        timestamp=timestamp or datetime.now(timezone.utc),
        sequence_number=sequence,
        schema_version=REMEDIAL_EVENT_SCHEMA_VERSION,
        payload=payload or {},
    )
    session.events.append(event)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def complete_session(db, session_id: uuid.UUID) -> PracticeSession:
    session = _require(db, session_id)
    if session.status in {STATUS_COMPLETED, STATUS_ABANDONED}:
        raise SessionError(
            f"Session '{session_id}' is already in state '{session.status}'.", status_code=409
        )
    # Record the terminal event while the session is still open, then flip.
    session.completed_at = datetime.now(timezone.utc)
    record_event(db, session.id, "SESSION_COMPLETED", payload={"activity_id": session.activity_id, "difficulty": session.difficulty}, session=session)
    session.status = STATUS_COMPLETED
    db.commit()
    db.refresh(session)
    return session


def abandon_session(db, session_id: uuid.UUID) -> PracticeSession:
    session = _require(db, session_id)
    if session.status in {STATUS_COMPLETED, STATUS_ABANDONED}:
        raise SessionError(
            f"Session '{session_id}' is already in state '{session.status}'.", status_code=409
        )
    session.completed_at = datetime.now(timezone.utc)
    record_event(db, session.id, "SESSION_ABANDONED", payload={"activity_id": session.activity_id, "difficulty": session.difficulty}, session=session)
    session.status = STATUS_ABANDONED
    db.commit()
    db.refresh(session)
    return session


def practice_history(db, child_id: uuid.UUID, limit: int | None = None) -> list[PracticeSession]:
    statement = (
        select(PracticeSession)
        .where(PracticeSession.child_id == child_id)
        .order_by(PracticeSession.completed_at.asc().nullsfirst())
    )
    result = list(db.execute(statement).scalars().all())
    return result[:limit] if limit is not None else result