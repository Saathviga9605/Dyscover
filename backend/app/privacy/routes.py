"""Privacy endpoints for GDPR/COPPA compliance: data export and deletion."""

from __future__ import annotations

import json
import zipfile
import io
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.routes import get_current_user
from app.audit import AuditEventType, AuditLogger
from app.database import get_db
from app.models import (
    User,
    ChildProfile,
    AssessmentSession,
    GameSession,
    Trial,
    InteractionEvent,
    GazeSample,
    Fixation,
    FeatureVector,
    SessionFeatureVector,
    AssessmentSummary,
    SpeechSession,
    PracticeSession,
    PracticeEvent,
    EducatorLearnerAssignment,
)

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


def serialize_model(obj: Any) -> dict[str, Any]:
    """Serialize a SQLAlchemy model to a dict."""
    if hasattr(obj, "__dict__"):
        result = {}
        for key, value in obj.__dict__.items():
            if key.startswith("_"):
                continue
            if isinstance(value, (datetime, UUID)):
                result[key] = str(value)
            elif isinstance(value, (str, int, float, bool, type(None))):
                result[key] = value
            elif isinstance(value, (list, dict)):
                result[key] = value
            else:
                try:
                    result[key] = str(value)
                except Exception:
                    pass
        return result
    return {}


def collect_user_data(db: Session, user_id: UUID) -> dict[str, Any]:
    """Collect all data associated with a user for export."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = {
        "user": serialize_model(user),
        "children": [],
        "educator_assignments": [],
    }

    # Children
    children = db.query(ChildProfile).filter(ChildProfile.owner_id == user_id).all()
    for child in children:
        child_data = serialize_model(child)

        # Assessments
        assessments = db.query(AssessmentSession).filter(AssessmentSession.child_id == child.id).all()
        child_data["assessments"] = []
        for assessment in assessments:
            assessment_data = serialize_model(assessment)

            # Game sessions
            game_sessions = db.query(GameSession).filter(GameSession.assessment_session_id == assessment.id).all()
            assessment_data["game_sessions"] = []
            for gs in game_sessions:
                gs_data = serialize_model(gs)

                # Trials
                trials = db.query(Trial).filter(Trial.game_session_id == gs.id).all()
                gs_data["trials"] = []
                for trial in trials:
                    trial_data = serialize_model(trial)

                    # Events
                    events = db.query(InteractionEvent).filter(InteractionEvent.trial_id == trial.id).all()
                    trial_data["events"] = [serialize_model(e) for e in events]

                    # Gaze samples
                    gaze_samples = db.query(GazeSample).filter(GazeSample.trial_id == trial.id).all()
                    trial_data["gaze_samples"] = [serialize_model(g) for g in gaze_samples]

                    # Fixations
                    fixations = db.query(Fixation).filter(Fixation.trial_id == trial.id).all()
                    trial_data["fixations"] = [serialize_model(f) for f in fixations]

                    # Feature vectors
                    fv = db.query(FeatureVector).filter(FeatureVector.trial_id == trial.id).first()
                    if fv:
                        trial_data["feature_vector"] = serialize_model(fv)

                    gs_data["trials"].append(trial_data)

                assessment_data["game_sessions"].append(gs_data)

            child_data["assessments"].append(assessment_data)

        data["children"].append(child_data)

    # Speech sessions
    speech_sessions = db.query(SpeechSession).filter(SpeechSession.assessment_id.in_(
        [a.id for a in db.query(AssessmentSession.id).filter(AssessmentSession.child_id.in_(
            [c.id for c in children]
        )).all()]
    )).all() if children else []
    data["speech_sessions"] = [serialize_model(s) for s in speech_sessions]

    # Practice sessions
    for child in children:
        practice_sessions = db.query(PracticeSession).filter(PracticeSession.child_id == child.id).all()
        for ps in practice_sessions:
            ps_data = serialize_model(ps)
            events = db.query(PracticeEvent).filter(PracticeEvent.practice_session_id == ps.id).all()
            ps_data["events"] = [serialize_model(e) for e in events]
            data.setdefault("practice_sessions", []).append(ps_data)

    # Educator assignments
    assignments = db.query(EducatorLearnerAssignment).filter(
        (EducatorLearnerAssignment.educator_id == user_id) | (EducatorLearnerAssignment.child_id.in_([c.id for c in children]))
    ).all()
    data["educator_assignments"] = [serialize_model(a) for a in assignments]

    return data


@router.get("/export", response_class=StreamingResponse)
async def export_user_data(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export all user data as a ZIP file (GDPR Article 20 - Right to data portability)."""
    audit = AuditLogger(request)

    try:
        data = collect_user_data(db, current_user.id)

        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Main data JSON
            zipf.writestr("user_data.json", json.dumps(data, indent=2, ensure_ascii=False))

            # Summary
            summary = {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "user_id": str(current_user.id),
                "children_count": len(data.get("children", [])),
                "assessments_count": sum(len(c.get("assessments", [])) for c in data.get("children", [])),
                "speech_sessions_count": len(data.get("speech_sessions", [])),
                "practice_sessions_count": len(data.get("practice_sessions", [])),
            }
            zipf.writestr("export_summary.json", json.dumps(summary, indent=2))

        zip_buffer.seek(0)

        audit.log(
            AuditEventType.DATA_EXPORT,
            user_id=str(current_user.id),
            resource_type="user_data",
            resource_id=str(current_user.id),
            success=True,
        )

        return StreamingResponse(
            io.BytesIO(zip_buffer.getvalue()),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="dyscover_export_{current_user.id}_{datetime.now().strftime("%Y%m%d")}.zip"'
            },
        )

    except Exception as e:
        audit.log(
            AuditEventType.DATA_EXPORT,
            user_id=str(current_user.id),
            success=False,
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail="Export failed")


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete user account and all associated data (GDPR Article 17 - Right to erasure / COPPA)."""
    audit = AuditLogger(request)

    try:
        user_id = str(current_user.id)

        # Collect data for audit log before deletion
        children_count = db.query(ChildProfile).filter(ChildProfile.owner_id == current_user.id).count()

        # Delete cascade will handle related records if foreign keys are set up with ON DELETE CASCADE
        # For now, manually delete in correct order
        # 1. Practice events
        child_ids = [c.id for c in db.query(ChildProfile).filter(ChildProfile.owner_id == current_user.id).all()]
        if child_ids:
            practice_session_ids = [ps.id for ps in db.query(PracticeSession).filter(PracticeSession.child_id.in_(child_ids)).all()]
            if practice_session_ids:
                db.query(PracticeEvent).filter(PracticeEvent.practice_session_id.in_(practice_session_ids)).delete(synchronize_session=False)
            db.query(PracticeSession).filter(PracticeSession.child_id.in_(child_ids)).delete(synchronize_session=False)

            # Speech sessions
            assessment_ids = [a.id for a in db.query(AssessmentSession).filter(AssessmentSession.child_id.in_(child_ids)).all()]
            if assessment_ids:
                db.query(SpeechSession).filter(SpeechSession.assessment_id.in_(assessment_ids)).delete(synchronize_session=False)

                # Trials and related data
                trial_ids = [t.id for t in db.query(Trial).filter(Trial.game_session_id.in_(
                    [gs.id for gs in db.query(GameSession).filter(GameSession.assessment_session_id.in_(assessment_ids)).all()]
                )).all()]
                if trial_ids:
                    db.query(InteractionEvent).filter(InteractionEvent.trial_id.in_(trial_ids)).delete(synchronize_session=False)
                    db.query(GazeSample).filter(GazeSample.trial_id.in_(trial_ids)).delete(synchronize_session=False)
                    db.query(Fixation).filter(Fixation.trial_id.in_(trial_ids)).delete(synchronize_session=False)
                    db.query(FeatureVector).filter(FeatureVector.trial_id.in_(trial_ids)).delete(synchronize_session=False)

                db.query(Trial).filter(Trial.game_session_id.in_(
                    [gs.id for gs in db.query(GameSession).filter(GameSession.assessment_session_id.in_(assessment_ids)).all()]
                )).delete(synchronize_session=False)

                db.query(GameSession).filter(GameSession.assessment_session_id.in_(assessment_ids)).delete(synchronize_session=False)

            db.query(AssessmentSession).filter(AssessmentSession.child_id.in_(child_ids)).delete(synchronize_session=False)

            db.query(ChildProfile).filter(ChildProfile.owner_id == current_user.id).delete(synchronize_session=False)

        # Educator assignments
        db.query(EducatorLearnerAssignment).filter(
            (EducatorLearnerAssignment.educator_id == current_user.id) |
            (EducatorLearnerAssignment.child_id.in_(child_ids))
        ).delete(synchronize_session=False)

        # Feature vectors and session feature vectors
        trial_ids_all = [t.id for t in db.query(Trial).filter(Trial.game_session_id.in_(
            [gs.id for gs in db.query(GameSession).filter(GameSession.assessment_session_id.in_(
                [a.id for a in db.query(AssessmentSession).filter(AssessmentSession.child_id.in_(child_ids)).all()]
            )).all()]
        )).all()] if child_ids else []
        if trial_ids_all:
            db.query(FeatureVector).filter(FeatureVector.trial_id.in_(trial_ids_all)).delete(synchronize_session=False)

        assessment_ids_all = [a.id for a in db.query(AssessmentSession).filter(AssessmentSession.child_id.in_(child_ids)).all()] if child_ids else []
        if assessment_ids_all:
            db.query(SessionFeatureVector).filter(SessionFeatureVector.assessment_id.in_(assessment_ids_all)).delete(synchronize_session=False)
            db.query(AssessmentSummary).filter(AssessmentSummary.assessment_id.in_(assessment_ids_all)).delete(synchronize_session=False)

        # Finally delete user
        db.delete(current_user)
        db.commit()

        audit.log(
            AuditEventType.DATA_DELETION,
            user_id=user_id,
            resource_type="user_account",
            resource_id=user_id,
            details={"children_deleted": children_count},
            success=True,
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        db.rollback()
        audit.log(
            AuditEventType.DATA_DELETION,
            user_id=str(current_user.id),
            success=False,
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail="Account deletion failed")


@router.get("/data-summary")
async def get_data_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get a summary of what data is stored for the user."""
    children = db.query(ChildProfile).filter(ChildProfile.owner_id == current_user.id).all()
    child_ids = [c.id for c in children]

    assessment_count = 0
    trial_count = 0
    event_count = 0
    speech_count = 0
    practice_count = 0

    if child_ids:
        assessment_ids = [a.id for a in db.query(AssessmentSession).filter(AssessmentSession.child_id.in_(child_ids)).all()]
        assessment_count = len(assessment_ids)

        if assessment_ids:
            game_session_ids = [gs.id for gs in db.query(GameSession).filter(GameSession.assessment_session_id.in_(assessment_ids)).all()]
            if game_session_ids:
                trial_ids = [t.id for t in db.query(Trial).filter(Trial.game_session_id.in_(game_session_ids)).all()]
                trial_count = len(trial_ids)
                if trial_ids:
                    event_count = db.query(InteractionEvent).filter(InteractionEvent.trial_id.in_(trial_ids)).count()
                    speech_count = db.query(SpeechSession).filter(SpeechSession.assessment_id.in_(assessment_ids)).count()

        practice_sessions = db.query(PracticeSession).filter(PracticeSession.child_id.in_(child_ids)).all()
        practice_count = len(practice_sessions)

    return {
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "role": current_user.role,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        },
        "children": {
            "count": len(children),
            "details": [
                {
                    "id": str(c.id),
                    "display_name": c.display_name,
                    "birth_year": c.birth_year,
                }
                for c in children
            ],
        },
        "assessments": {"count": assessment_count},
        "trials": {"count": trial_count},
        "interaction_events": {"count": event_count},
        "speech_sessions": {"count": speech_count},
        "practice_sessions": {"count": practice_count},
    }