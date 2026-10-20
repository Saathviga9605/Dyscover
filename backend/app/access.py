"""Resource-level authorization.

Every child-owned record resolves to a ``ChildProfile`` and is accessible only to:
- the child's owner (parent account) — full access;
- an educator with an *active* assignment granted by that owner — read-only, and
  only where the caller passes ``allow_educator=True`` (aggregated summaries,
  personalization views). Raw assessment traces stay owner-only.

Denials raise 404 rather than 403 so that knowing (or guessing) an ID reveals
nothing about whether the record exists.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AssessmentSession,
    ChildProfile,
    EducatorLearnerAssignment,
    GameSession,
    PracticeSession,
    SpeechSession,
    Trial,
    User,
)


def _not_found(kind: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{kind} not found")


def _parse_uuid(value: UUID | str, kind: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        raise _not_found(kind)


def has_active_educator_assignment(db: Session, educator_id: UUID, child_id: UUID) -> bool:
    return db.scalar(
        select(EducatorLearnerAssignment.id).where(
            EducatorLearnerAssignment.educator_id == educator_id,
            EducatorLearnerAssignment.child_id == child_id,
            EducatorLearnerAssignment.status == "active",
        )
    ) is not None


def can_access_child(db: Session, user: User, child: ChildProfile, allow_educator: bool = False) -> bool:
    if child.owner_id is not None and child.owner_id == user.id:
        return True
    if allow_educator and user.role == "educator":
        return has_active_educator_assignment(db, user.id, child.id)
    return False


def get_child_for_user(db: Session, user: User, child_id: UUID | str, allow_educator: bool = False) -> ChildProfile:
    child = db.get(ChildProfile, _parse_uuid(child_id, "Child profile"))
    if child is None or not can_access_child(db, user, child, allow_educator):
        raise _not_found("Child profile")
    return child


def get_assessment_for_user(db: Session, user: User, assessment_id: UUID | str, allow_educator: bool = False) -> AssessmentSession:
    assessment = db.get(AssessmentSession, _parse_uuid(assessment_id, "Assessment session"))
    if assessment is None or not can_access_child(db, user, assessment.child, allow_educator):
        raise _not_found("Assessment session")
    return assessment


def get_game_session_for_user(db: Session, user: User, game_session_id: UUID | str) -> GameSession:
    game = db.get(GameSession, _parse_uuid(game_session_id, "Game session"))
    if game is None or not can_access_child(db, user, game.assessment.child):
        raise _not_found("Game session")
    return game


def get_trial_for_user(db: Session, user: User, trial_id: UUID | str) -> Trial:
    trial = db.get(Trial, _parse_uuid(trial_id, "Trial"))
    if trial is None or not can_access_child(db, user, trial.game_session.assessment.child):
        raise _not_found("Trial")
    return trial


def get_speech_session_for_user(db: Session, user: User, speech_session_id: UUID | str) -> SpeechSession:
    speech = db.get(SpeechSession, _parse_uuid(speech_session_id, "Speech session"))
    if speech is None:
        raise _not_found("Speech session")
    assessment = db.get(AssessmentSession, speech.assessment_id)
    if assessment is None or not can_access_child(db, user, assessment.child):
        raise _not_found("Speech session")
    return speech


def get_practice_session_for_user(db: Session, user: User, session_id: UUID | str) -> PracticeSession:
    session = db.get(PracticeSession, _parse_uuid(session_id, "Practice session"))
    if session is None or not can_access_child(db, user, session.child):
        raise _not_found("Practice session")
    return session
