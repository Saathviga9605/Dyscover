"""Data export and deletion.

Deletion policy (documented in docs/privacy.md): deleting a child removes every
record derived from that child; deleting an account removes the account, its
children (and everything derived from them), its Lexi conversations, its
refresh tokens and every educator assignment it is part of. Nothing is
soft-deleted or retained. Callers commit; a failure leaves nothing deleted.

Rows are deleted explicitly in dependency order rather than relying on database
cascades, because SQLite databases created before the cascade declarations
lack ``ON DELETE CASCADE``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.models import (
    AssessmentSession,
    AssessmentSummary,
    ChildProfile,
    Conversation,
    EducatorLearnerAssignment,
    FeatureVector,
    Fixation,
    GameSession,
    GazeSample,
    InteractionEvent,
    Message,
    PracticeEvent,
    PracticeSession,
    RefreshToken,
    SessionFeatureVector,
    SpeechSession,
    Trial,
    User,
)

EXPORT_SCHEMA_VERSION = "2.0"

# Columns that must never leave the server.
_USER_EXPORT_FIELDS = ("id", "email", "display_name", "role", "is_active", "created_at")


def delete_children(db: Session, child_ids: Iterable[UUID]) -> int:
    child_ids = list(child_ids)
    if not child_ids:
        return 0
    assessments = select(AssessmentSession.id).where(AssessmentSession.child_id.in_(child_ids))
    games = select(GameSession.id).where(GameSession.assessment_session_id.in_(assessments))
    trials = select(Trial.id).where(Trial.game_session_id.in_(games))
    practice = select(PracticeSession.id).where(PracticeSession.child_id.in_(child_ids))

    for statement in (
        delete(InteractionEvent).where(or_(InteractionEvent.trial_id.in_(trials), InteractionEvent.session_id.in_(assessments))),
        delete(GazeSample).where(GazeSample.trial_id.in_(trials)),
        delete(Fixation).where(Fixation.trial_id.in_(trials)),
        delete(FeatureVector).where(FeatureVector.trial_id.in_(trials)),
        delete(SpeechSession).where(or_(SpeechSession.assessment_id.in_(assessments), SpeechSession.trial_id.in_(trials))),
        delete(Trial).where(Trial.game_session_id.in_(games)),
        delete(GameSession).where(GameSession.assessment_session_id.in_(assessments)),
        delete(SessionFeatureVector).where(SessionFeatureVector.assessment_id.in_(assessments)),
        delete(AssessmentSummary).where(AssessmentSummary.assessment_id.in_(assessments)),
        delete(AssessmentSession).where(AssessmentSession.child_id.in_(child_ids)),
        delete(PracticeEvent).where(PracticeEvent.practice_session_id.in_(practice)),
        delete(PracticeSession).where(PracticeSession.child_id.in_(child_ids)),
        delete(EducatorLearnerAssignment).where(EducatorLearnerAssignment.child_id.in_(child_ids)),
    ):
        db.execute(statement.execution_options(synchronize_session=False))
    result = db.execute(delete(ChildProfile).where(ChildProfile.id.in_(child_ids)).execution_options(synchronize_session=False))
    db.expire_all()
    return result.rowcount or 0


def delete_account(db: Session, user: User) -> dict[str, int]:
    user_id = user.id
    child_ids = list(db.scalars(select(ChildProfile.id).where(ChildProfile.owner_id == user_id)))
    conversations = select(Conversation.id).where(Conversation.user_id == user_id)
    children_deleted = delete_children(db, child_ids)
    conversation_count = len(db.scalars(conversations).all())
    for statement in (
        delete(Message).where(Message.conversation_id.in_(conversations)),
        delete(Conversation).where(Conversation.user_id == user_id),
        delete(RefreshToken).where(RefreshToken.user_id == user_id),
        delete(EducatorLearnerAssignment).where(EducatorLearnerAssignment.educator_id == user_id),
        delete(User).where(User.id == user_id),
    ):
        db.execute(statement.execution_options(synchronize_session=False))
    db.expire_all()
    return {"children_deleted": children_deleted, "conversations_deleted": conversation_count}


def _serialize(obj: Any, fields: Iterable[str] | None = None) -> dict[str, Any]:
    columns = fields or [column.key for column in obj.__mapper__.column_attrs]
    out: dict[str, Any] = {}
    for key in columns:
        value = getattr(obj, key)
        out[key] = value.isoformat() if isinstance(value, datetime) else str(value) if isinstance(value, UUID) else value
    return out


def collect_user_data(db: Session, user: User) -> dict[str, Any]:
    """Everything stored about this account and the children it owns."""
    children = list(db.scalars(select(ChildProfile).where(ChildProfile.owner_id == user.id)))
    exported_children = []
    for child in children:
        child_data = _serialize(child)
        child_data["assessments"] = []
        for assessment in db.scalars(select(AssessmentSession).where(AssessmentSession.child_id == child.id)):
            assessment_data = _serialize(assessment)
            summary = db.scalar(select(AssessmentSummary).where(AssessmentSummary.assessment_id == assessment.id))
            assessment_data["summary"] = _serialize(summary) if summary else None
            features = db.scalar(select(SessionFeatureVector).where(SessionFeatureVector.assessment_id == assessment.id))
            assessment_data["session_features"] = _serialize(features) if features else None
            assessment_data["speech_sessions"] = [_serialize(row) for row in db.scalars(select(SpeechSession).where(SpeechSession.assessment_id == assessment.id))]
            assessment_data["game_sessions"] = []
            for game in db.scalars(select(GameSession).where(GameSession.assessment_session_id == assessment.id)):
                game_data = _serialize(game)
                game_data["trials"] = []
                for trial in db.scalars(select(Trial).where(Trial.game_session_id == game.id).order_by(Trial.trial_number)):
                    trial_data = _serialize(trial)
                    trial_data["events"] = [_serialize(row) for row in db.scalars(select(InteractionEvent).where(InteractionEvent.trial_id == trial.id))]
                    trial_data["gaze_samples"] = [_serialize(row) for row in db.scalars(select(GazeSample).where(GazeSample.trial_id == trial.id))]
                    trial_data["fixations"] = [_serialize(row) for row in db.scalars(select(Fixation).where(Fixation.trial_id == trial.id))]
                    game_data["trials"].append(trial_data)
                assessment_data["game_sessions"].append(game_data)
            child_data["assessments"].append(assessment_data)
        child_data["practice_sessions"] = []
        for session in db.scalars(select(PracticeSession).where(PracticeSession.child_id == child.id)):
            session_data = _serialize(session)
            session_data["events"] = [_serialize(row) for row in db.scalars(select(PracticeEvent).where(PracticeEvent.practice_session_id == session.id))]
            child_data["practice_sessions"].append(session_data)
        child_data["educator_access"] = [
            {"educator_id": str(row.educator_id), "status": row.status, "created_at": row.created_at.isoformat(), "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None}
            for row in db.scalars(select(EducatorLearnerAssignment).where(EducatorLearnerAssignment.child_id == child.id))
        ]
        exported_children.append(child_data)

    conversations = []
    for conversation in db.scalars(select(Conversation).where(Conversation.user_id == user.id)):
        conversation_data = _serialize(conversation)
        conversation_data["messages"] = [_serialize(message) for message in conversation.messages]
        conversations.append(conversation_data)

    educator_assignments = [
        {"child_id": str(row.child_id), "status": row.status, "created_at": row.created_at.isoformat()}
        for row in db.scalars(select(EducatorLearnerAssignment).where(EducatorLearnerAssignment.educator_id == user.id))
    ]
    return {
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "user": _serialize(user, _USER_EXPORT_FIELDS),
        "children": exported_children,
        "lexi_conversations": conversations,
        "educator_assignments": educator_assignments,
    }
