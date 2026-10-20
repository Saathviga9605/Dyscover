"""Educator workspace: read-only, aggregated summaries of learners whose
parents granted access. Raw trials, events, gaze and speech data are never
exposed here."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import AuditEventType, AuditLogger
from app.auth.deps import require_roles
from app.core.time import utcnow
from app.database import get_db
from app.models import AssessmentSession, ChildProfile, EducatorLearnerAssignment, GameSession, PracticeSession, Trial, User

router = APIRouter(prefix="/api/educator", tags=["educator"])

MIN_TRIALS_FOR_SUMMARY = 3

require_educator = require_roles("educator")


def summarize_learner(db: Session, child: ChildProfile) -> dict:
    assessments = list(db.scalars(select(AssessmentSession).where(AssessmentSession.child_id == child.id)))
    completed = [assessment for assessment in assessments if assessment.status == "completed"]
    assessment_ids = [assessment.id for assessment in assessments]
    game_ids = list(db.scalars(select(GameSession.id).where(GameSession.assessment_session_id.in_(assessment_ids)))) if assessment_ids else []
    trials = list(db.scalars(select(Trial).where(Trial.game_session_id.in_(game_ids)))) if game_ids else []

    domain_totals: dict[str, dict[str, int]] = {}
    for trial in trials:
        if not trial.domain:
            continue
        bucket = domain_totals.setdefault(trial.domain, {"count": 0, "scored": 0, "correct": 0})
        bucket["count"] += 1
        if trial.correctness is not None:
            bucket["scored"] += 1
            bucket["correct"] += 1 if trial.correctness else 0

    domains = []
    for domain, values in sorted(domain_totals.items()):
        sufficient = values["scored"] >= MIN_TRIALS_FOR_SUMMARY
        domains.append({
            "domain": domain,
            "evidence_trials": values["count"],
            # Accuracy is only reported once enough scored trials exist.
            "accuracy": round(values["correct"] / values["scored"] * 100, 1) if sufficient else None,
            "quality": "sufficient" if sufficient else "insufficient",
        })

    practice_sessions = list(db.scalars(select(PracticeSession).where(PracticeSession.child_id == child.id)))
    activities = sorted({session.activity_id for session in practice_sessions if session.activity_id})
    if not assessments:
        observation_summary = "No observations recorded yet."
    elif not domains:
        observation_summary = "Not enough activity evidence to summarize yet."
    else:
        observation_summary = "Activity observations are available. They describe performance in games, not a diagnosis."

    return {
        "child_id": str(child.id),
        "display_name": child.display_name,
        "completed_assessment_count": len(completed),
        "language_context": sorted({assessment.language for assessment in assessments if assessment.language}),
        "observation_summary": observation_summary,
        "domains": domains,
        "practice_summary": {
            "completed_sessions": sum(1 for session in practice_sessions if session.status == "completed"),
            "activity_count": len(activities),
            "activities": activities,
        },
    }


def _active_assignment(db: Session, educator: User, child_id: UUID) -> EducatorLearnerAssignment:
    assignment = db.scalar(
        select(EducatorLearnerAssignment).where(
            EducatorLearnerAssignment.educator_id == educator.id,
            EducatorLearnerAssignment.child_id == child_id,
            EducatorLearnerAssignment.status == "active",
        )
    )
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner not found")
    return assignment


@router.get("/learners", response_model=list[dict])
def list_learners(educator: User = Depends(require_educator), db: Session = Depends(get_db)) -> list[dict]:
    assignments = db.scalars(
        select(EducatorLearnerAssignment)
        .where(EducatorLearnerAssignment.educator_id == educator.id, EducatorLearnerAssignment.status == "active")
        .order_by(EducatorLearnerAssignment.created_at.desc())
    )
    return [summarize_learner(db, assignment.child) for assignment in assignments]


@router.get("/learners/{child_id}/summary", response_model=dict)
def learner_summary(child_id: UUID, educator: User = Depends(require_educator), db: Session = Depends(get_db)) -> dict:
    assignment = _active_assignment(db, educator, child_id)
    return summarize_learner(db, assignment.child)


@router.post("/learners/{child_id}/revoke", status_code=status.HTTP_204_NO_CONTENT)
def leave_learner(child_id: UUID, request: Request, educator: User = Depends(require_educator), db: Session = Depends(get_db)) -> Response:
    """An educator can relinquish their own access; they can never grant it."""
    assignment = _active_assignment(db, educator, child_id)
    assignment.status = "revoked"
    assignment.revoked_at = utcnow()
    assignment.revocation_reason = "educator revocation"
    db.commit()
    AuditLogger(request).log(AuditEventType.EDUCATOR_REVOKE, user_id=str(educator.id), resource_type="child", resource_id=str(child_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
